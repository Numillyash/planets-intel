from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from typing import Any, Mapping

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.battle_simulator_planet import (
    PLANET_CARRYOVER_BASIS,
    apply_planet_carryover,
    rebuild_planet_combatant,
)
from app.services.vcr_replay import ReplayUnsupported
from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog

SAMPLE_LIMIT = 8
FIELD_MAP = {
    "beam_count": "beamcount",
    "launcher_count": "launchercount",
    "bay_count": "baycount",
    "beam_id": "beamid",
    "torpedo_id": "torpedoid",
    "shield": "shield",
    "damage": "damage",
    "crew": "crew",
    "mass": "mass",
    "fighters": "fighters",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only regression diagnostic for repeated same-turn planetary VCRs."
    )
    parser.add_argument("--game-id", type=int, default=None)
    parser.add_argument("--all", action="store_true")
    return parser.parse_args()


def _int(record: Mapping[str, Any] | None, key: str) -> int | None:
    if not isinstance(record, Mapping):
        return None
    value = record.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _bool(record: Mapping[str, Any] | None, key: str) -> bool | None:
    if not isinstance(record, Mapping):
        return None
    value = record.get(key)
    return value if isinstance(value, bool) else None


def _infer_no_starbase_start(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if _bool(raw, "hasstarbase") is not False:
        return None
    mass = _int(raw, "mass")
    shield = _int(raw, "shield")
    if mass is None or mass < 100 or shield is None:
        return None
    return rebuild_planet_combatant(
        {
            "hull_id": 0,
            "race_id": _int(raw, "raceid"),
            "has_starbase": False,
            "planet_defense": mass - 100,
        },
        shield=shield,
    )


def _projection_check(predicted: Mapping[str, Any], raw: Mapping[str, Any]) -> dict[str, Any]:
    comparable: list[str] = []
    mismatches: list[str] = []
    fields: dict[str, Any] = {}
    for predicted_key, raw_key in FIELD_MAP.items():
        expected = predicted.get(predicted_key)
        expected = expected if isinstance(expected, int) and not isinstance(expected, bool) else None
        actual = _int(raw, raw_key)
        match = expected == actual if expected is not None and actual is not None else None
        if match is not None:
            comparable.append(raw_key)
            if not match:
                mismatches.append(raw_key)
        fields[raw_key] = {"predicted": expected, "factual": actual, "matches": match}
    expected_base = predicted.get("has_starbase")
    expected_base = expected_base if isinstance(expected_base, bool) else None
    actual_base = _bool(raw, "hasstarbase")
    base_match = expected_base == actual_base if expected_base is not None and actual_base is not None else None
    if base_match is not None:
        comparable.append("hasstarbase")
        if not base_match:
            mismatches.append("hasstarbase")
    fields["hasstarbase"] = {
        "predicted": expected_base,
        "factual": actual_base,
        "matches": base_match,
    }
    return {
        "status": "not_comparable" if not comparable else ("mismatch" if mismatches else "match"),
        "comparable_fields": comparable,
        "mismatches": mismatches,
        "fields": fields,
    }


def _same_position(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    pa, pb = a.get("position"), b.get("position")
    return (
        isinstance(pa, list)
        and isinstance(pb, list)
        and len(pa) == len(pb) == 2
        and all(value is not None for value in pa + pb)
        and pa == pb
    )


def _transition(previous: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    terminal = previous["terminal"]
    next_start = current["start"]
    result: dict[str, Any] = {
        "game_id": previous["game_id"],
        "turn": previous["turn"],
        "planet_id": previous["planet_id"],
        "name": previous.get("name") or current.get("name"),
        "position": previous["position"],
        "from_vcr": previous["vcr_id"],
        "to_vcr": current["vcr_id"],
        "has_starbase": previous.get("has_starbase"),
    }
    if terminal.get("destroyed") or terminal.get("captured"):
        result["status"] = "reappearance_after_defeat"
        return result

    terminal_shield = terminal.get("shield")
    terminal_shield = terminal_shield if isinstance(terminal_shield, int) and not isinstance(terminal_shield, bool) else None
    next_shield = _int(next_start, "shield")
    shield_match = terminal_shield == next_shield if terminal_shield is not None and next_shield is not None else None
    result["shield_carry"] = {
        "terminal": terminal_shield,
        "next_start": next_shield,
        "matches": shield_match,
    }

    inferred = _infer_no_starbase_start(previous["start"])
    if inferred is None:
        result["exact_no_starbase"] = {"status": "not_applicable"}
        result["status"] = "mismatch" if shield_match is False else ("match" if shield_match is True else "not_comparable")
        return result

    start_check = _projection_check(inferred, previous["start"])
    if start_check["status"] != "match":
        result["exact_no_starbase"] = {
            "status": "start_reconstruction_mismatch",
            "start_reconstruction": start_check,
        }
        result["status"] = "mismatch" if shield_match is False else "not_comparable"
        return result

    predicted = apply_planet_carryover(inferred, inferred, terminal)
    next_check = _projection_check(predicted, next_start)
    result["exact_no_starbase"] = {
        "status": next_check["status"],
        "basis": PLANET_CARRYOVER_BASIS,
        "start_planet_defense": inferred.get("planet_defense"),
        "predicted_next_planet_defense": predicted.get("planet_defense"),
        "comparison": next_check,
    }
    if shield_match is False or next_check["status"] == "mismatch":
        result["status"] = "mismatch"
    elif shield_match is True and next_check["status"] == "match":
        result["status"] = "match"
    else:
        result["status"] = "not_comparable"
    return result


def run(args: argparse.Namespace) -> dict[str, Any]:
    with SessionLocal() as session:
        query = select(CombatObservation, PrivateObservationBatch).join(
            PrivateObservationBatch,
            PrivateObservationBatch.id == CombatObservation.batch_id,
        )
        if args.game_id is not None:
            query = query.where(PrivateObservationBatch.game_id == args.game_id)
        rows = session.execute(query.order_by(
            PrivateObservationBatch.game_id,
            CombatObservation.battle_turn,
            CombatObservation.vcr_id,
            PrivateObservationBatch.observed_at.desc(),
            PrivateObservationBatch.id.desc(),
        )).all()
        game_ids = sorted({int(batch.game_id) for _combat, batch in rows})
        catalogs = {
            int(catalog.game_id): catalog
            for catalog in session.execute(
                select(GameRuleCatalog).where(GameRuleCatalog.game_id.in_(game_ids))
            ).scalars().all()
        } if game_ids else {}

    grouped: dict[tuple[int, int, int], list[tuple[CombatObservation, PrivateObservationBatch]]] = defaultdict(list)
    for combat, batch in rows:
        grouped[(int(batch.game_id), int(combat.battle_turn), int(combat.vcr_id))].append((combat, batch))

    appearances: list[dict[str, Any]] = []
    supported = unsupported = catalog_missing = 0
    for (game_id, turn, vcr_id), observations in sorted(grouped.items()):
        combat, _batch = observations[0]
        payload = dict(combat.payload) if isinstance(combat.payload, dict) else {}
        catalog = catalogs.get(game_id)
        if catalog is None:
            catalog_missing += 1
            continue
        try:
            replay = replay_nuhost_from_nu_catalog(
                payload,
                beams=list(catalog.beams),
                torpedoes=list(catalog.torpedos),
                settings=dict(catalog.settings),
            )
        except ReplayUnsupported:
            unsupported += 1
            continue
        supported += 1
        for side_name in ("left", "right"):
            raw = payload.get(side_name)
            terminal = replay.get(side_name)
            if not isinstance(raw, Mapping) or not isinstance(terminal, Mapping):
                continue
            hull_id = _int(raw, "hullid")
            planet_id = _int(raw, "objectid")
            if hull_id is None or hull_id > 0 or planet_id is None:
                continue
            appearances.append({
                "game_id": game_id,
                "turn": turn,
                "vcr_id": vcr_id,
                "planet_id": planet_id,
                "position": [combat.x, combat.y],
                "name": raw.get("name") if isinstance(raw.get("name"), str) else None,
                "has_starbase": _bool(raw, "hasstarbase"),
                "start": dict(raw),
                "terminal": dict(terminal),
            })

    chains: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for item in appearances:
        chains[(item["game_id"], item["turn"], item["planet_id"])].append(item)

    transitions: list[dict[str, Any]] = []
    candidate_chains = skipped_location = 0
    for chain in chains.values():
        chain.sort(key=lambda item: item["vcr_id"])
        if len(chain) < 2:
            continue
        candidate_chains += 1
        for previous, current in zip(chain, chain[1:]):
            if not _same_position(previous, current):
                skipped_location += 1
                continue
            transitions.append(_transition(previous, current))

    summary = {
        "stored_observations": len(rows),
        "unique_vcrs": len(grouped),
        "catalog_missing": catalog_missing,
        "replay_supported": supported,
        "replay_unsupported": unsupported,
        "planet_appearances": len(appearances),
        "candidate_same_turn_planet_chains": candidate_chains,
        "same_location_transitions": len(transitions),
        "skipped_location_change": skipped_location,
        "matches": 0,
        "mismatches": 0,
        "not_comparable": 0,
        "reappearance_after_defeat": 0,
        "shield_matches": 0,
        "shield_mismatches": 0,
        "no_starbase_exact_matches": 0,
        "no_starbase_exact_mismatches": 0,
        "no_starbase_exact_not_comparable": 0,
        "starbase_or_unknown_transitions": 0,
    }
    details: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    for item in transitions:
        status = item.get("status")
        if status == "match":
            summary["matches"] += 1
            if len(samples) < SAMPLE_LIMIT:
                samples.append(item)
        elif status == "mismatch":
            summary["mismatches"] += 1
            details.append(item)
        elif status == "reappearance_after_defeat":
            summary["reappearance_after_defeat"] += 1
            details.append(item)
        else:
            summary["not_comparable"] += 1

        shield = item.get("shield_carry")
        if isinstance(shield, Mapping):
            if shield.get("matches") is True:
                summary["shield_matches"] += 1
            elif shield.get("matches") is False:
                summary["shield_mismatches"] += 1

        exact = item.get("exact_no_starbase")
        if isinstance(exact, Mapping):
            exact_status = exact.get("status")
            if exact_status == "match":
                summary["no_starbase_exact_matches"] += 1
            elif exact_status == "mismatch":
                summary["no_starbase_exact_mismatches"] += 1
            elif exact_status == "not_applicable":
                summary["starbase_or_unknown_transitions"] += 1
            else:
                summary["no_starbase_exact_not_comparable"] += 1

    return {
        "diagnostic": "combat_planet_chain_regression",
        "read_only": True,
        "filters": {"game_id": args.game_id, "include_all_details": bool(args.all)},
        "summary": summary,
        "details": transitions if args.all else details,
        "match_samples": samples,
        "notes": [
            "Shield carry is compared directly for every surviving repeated planetary defender.",
            "Exact carry is attempted only when hasstarbase is explicitly false and factual mass/shield are available.",
            "For non-starbase worlds, planet defense is inferred as combat mass minus 100 only after the inferred state reproduces the factual first VCR setup.",
            "Starbase transitions remain fail-closed because VCR state does not uniquely expose persistent base defense/fighters/tech/damage.",
            "No factual observations are modified.",
        ],
    }


def main() -> None:
    json.dump(run(parse_args()), sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
