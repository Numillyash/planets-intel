from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.combat_state_observation import CombatStateObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.vcr_replay import ReplayUnsupported, combat_rng_from_settings
from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only regression diagnostic for persisted factual VCRs. "
            "It measures deterministic replay coverage, reports payload conflicts "
            "between observers, and compares replay terminal ammunition with any "
            "analyst-confirmed combat-state observations."
        )
    )
    parser.add_argument(
        "--game-id",
        type=int,
        default=None,
        help="Restrict the diagnostic to one game. Default: all games with stored VCRs.",
    )
    parser.add_argument(
        "--turn",
        type=int,
        default=None,
        help="Restrict the diagnostic to one battle turn.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include every replayed VCR in details, not only interesting cases.",
    )
    return parser.parse_args()


def _payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:16]


def _integer(record: dict[str, Any] | None, key: str) -> int | None:
    if not isinstance(record, dict):
        return None
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _text(record: dict[str, Any] | None, key: str) -> str | None:
    if not isinstance(record, dict):
        return None
    value = record.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _side_summary(payload: dict[str, Any], side_name: str) -> dict[str, Any]:
    side = payload.get(side_name)
    if not isinstance(side, dict):
        return {"present": False}
    return {
        "present": True,
        "object_id": _integer(side, "objectid"),
        "name": _text(side, "name"),
        "hull_id": _integer(side, "hullid"),
        "race_id": _integer(side, "raceid"),
        "beam_count": _integer(side, "beamcount"),
        "launcher_count": _integer(side, "launchercount"),
        "bay_count": _integer(side, "baycount"),
        "torpedoes": _integer(side, "torpedos"),
        "fighters": _integer(side, "fighters"),
        "shield": _integer(side, "shield"),
        "damage": _integer(side, "damage"),
        "crew": _integer(side, "crew"),
        "mass": _integer(side, "mass"),
    }


def _replay_side_for_ship(
    payload: dict[str, Any],
    replay: dict[str, Any],
    ship_id: int,
) -> tuple[str, dict[str, Any]] | None:
    matches: list[tuple[str, dict[str, Any]]] = []
    for side_name in ("left", "right"):
        raw_side = payload.get(side_name)
        replay_side = replay.get(side_name)
        if not isinstance(raw_side, dict) or not isinstance(replay_side, dict):
            continue
        if _integer(raw_side, "hullid") in (None, 0):
            continue
        if _integer(raw_side, "objectid") == ship_id:
            matches.append((side_name, replay_side))
    return matches[0] if len(matches) == 1 else None


def _compare_analyst_state(
    *,
    payload: dict[str, Any],
    replay: dict[str, Any],
    rows: list[CombatStateObservation],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for row in rows:
        located = _replay_side_for_ship(payload, replay, int(row.ship_id))
        if located is None:
            checks.append(
                {
                    "user_id": int(row.user_id),
                    "ship_id": int(row.ship_id),
                    "status": "not_comparable",
                    "reason": "ship is absent or ambiguous in selected factual VCR payload",
                }
            )
            continue

        side_name, replay_side = located
        asserted: dict[str, int] = {}
        actual: dict[str, Any] = {}
        mismatches: list[str] = []

        if row.post_combat_torpedoes is not None:
            asserted["torpedoes"] = int(row.post_combat_torpedoes)
            actual["torpedoes"] = replay_side.get("torpedoes")
            if actual["torpedoes"] != asserted["torpedoes"]:
                mismatches.append("torpedoes")
        if row.post_combat_fighters is not None:
            asserted["fighters"] = int(row.post_combat_fighters)
            actual["fighters"] = replay_side.get("fighters")
            if actual["fighters"] != asserted["fighters"]:
                mismatches.append("fighters")

        if not asserted:
            status = "no_asserted_values"
        elif mismatches:
            status = "mismatch"
        else:
            status = "match"

        checks.append(
            {
                "user_id": int(row.user_id),
                "ship_id": int(row.ship_id),
                "side": side_name,
                "status": status,
                "asserted": asserted,
                "replay": actual,
                "mismatches": mismatches,
                "note": row.note,
            }
        )
    return checks


def run(args: argparse.Namespace) -> dict[str, Any]:
    with SessionLocal() as session:
        query = (
            select(
                CombatObservation,
                PrivateObservationBatch,
                PlanetsAccount,
            )
            .join(
                PrivateObservationBatch,
                PrivateObservationBatch.id == CombatObservation.batch_id,
            )
            .join(
                PlanetsAccount,
                PlanetsAccount.id
                == PrivateObservationBatch.observer_planets_account_id,
            )
        )
        if args.game_id is not None:
            query = query.where(PrivateObservationBatch.game_id == args.game_id)
        if args.turn is not None:
            query = query.where(CombatObservation.battle_turn == args.turn)
        query = query.order_by(
            PrivateObservationBatch.game_id,
            CombatObservation.battle_turn.desc(),
            CombatObservation.vcr_id.desc(),
            PrivateObservationBatch.observed_at.desc(),
            PrivateObservationBatch.id.desc(),
        )
        rows = session.execute(query).all()

        game_ids = sorted(
            {
                int(batch.game_id)
                for _combat, batch, _account in rows
            }
        )
        catalogs = {
            int(catalog.game_id): catalog
            for catalog in session.execute(
                select(GameRuleCatalog).where(GameRuleCatalog.game_id.in_(game_ids))
            ).scalars().all()
        } if game_ids else {}

        analyst_query = select(CombatStateObservation)
        if game_ids:
            analyst_query = analyst_query.where(
                CombatStateObservation.game_id.in_(game_ids)
            )
        else:
            analyst_query = analyst_query.where(False)
        if args.turn is not None:
            analyst_query = analyst_query.where(
                CombatStateObservation.turn == args.turn
            )
        analyst_rows = session.execute(analyst_query).scalars().all()

    analyst_by_battle: dict[
        tuple[int, int, int],
        list[CombatStateObservation],
    ] = defaultdict(list)
    for row in analyst_rows:
        analyst_by_battle[
            (int(row.game_id), int(row.turn), int(row.vcr_id))
        ].append(row)

    grouped: dict[
        tuple[int, int, int],
        list[tuple[CombatObservation, PrivateObservationBatch, PlanetsAccount]],
    ] = defaultdict(list)
    for combat, batch, account in rows:
        grouped[
            (int(batch.game_id), int(combat.battle_turn), int(combat.vcr_id))
        ].append((combat, batch, account))

    summary = {
        "stored_observations": len(rows),
        "unique_vcrs": len(grouped),
        "payload_conflicts": 0,
        "catalog_missing": 0,
        "replay_supported": 0,
        "replay_unsupported": 0,
        "analyst_checks": 0,
        "analyst_matches": 0,
        "analyst_mismatches": 0,
        "analyst_not_comparable": 0,
    }
    by_game: dict[str, dict[str, Any]] = {}
    details: list[dict[str, Any]] = []

    for key in sorted(grouped, key=lambda item: (item[0], -item[1], -item[2])):
        game_id, turn, vcr_id = key
        observations = grouped[key]
        selected_combat, selected_batch, _selected_account = observations[0]
        selected_payload = (
            dict(selected_combat.payload)
            if isinstance(selected_combat.payload, dict)
            else {}
        )

        hashes: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for combat, batch, account in observations:
            payload = dict(combat.payload) if isinstance(combat.payload, dict) else {}
            payload_hash = _payload_hash(payload)
            hashes[payload_hash].append(
                {
                    "observer": account.planets_username,
                    "account_id": int(account.id),
                    "batch_id": int(batch.id),
                    "observed_at": batch.observed_at.isoformat(),
                }
            )
        payload_conflict = len(hashes) > 1
        if payload_conflict:
            summary["payload_conflicts"] += 1

        game_summary = by_game.setdefault(
            str(game_id),
            {
                "unique_vcrs": 0,
                "replay_supported": 0,
                "replay_unsupported": 0,
                "payload_conflicts": 0,
                "combat_rng": None,
                "catalog_observed_turn": None,
            },
        )
        game_summary["unique_vcrs"] += 1
        if payload_conflict:
            game_summary["payload_conflicts"] += 1

        case: dict[str, Any] = {
            "game_id": game_id,
            "turn": turn,
            "vcr_id": vcr_id,
            "battle_type": selected_combat.battle_type,
            "position": [selected_combat.x, selected_combat.y],
            "seed": _integer(selected_payload, "seed"),
            "left": _side_summary(selected_payload, "left"),
            "right": _side_summary(selected_payload, "right"),
            "source_observations": len(observations),
            "payload_variants": [
                {
                    "hash": payload_hash,
                    "sources": sources,
                }
                for payload_hash, sources in sorted(hashes.items())
            ],
            "payload_conflict": payload_conflict,
        }

        catalog = catalogs.get(game_id)
        if catalog is None:
            summary["catalog_missing"] += 1
            summary["replay_unsupported"] += 1
            game_summary["replay_unsupported"] += 1
            case["replay"] = {
                "supported": False,
                "reason": "game rule catalog is missing",
            }
            details.append(case)
            continue

        game_summary["combat_rng"] = combat_rng_from_settings(catalog.settings)
        game_summary["catalog_observed_turn"] = int(catalog.observed_turn)

        try:
            replay = replay_nuhost_from_nu_catalog(
                selected_payload,
                beams=list(catalog.beams),
                torpedoes=list(catalog.torpedos),
                settings=dict(catalog.settings),
            )
        except ReplayUnsupported as exc:
            summary["replay_unsupported"] += 1
            game_summary["replay_unsupported"] += 1
            case["replay"] = {
                "supported": False,
                "reason": str(exc),
            }
            details.append(case)
            continue

        summary["replay_supported"] += 1
        game_summary["replay_supported"] += 1
        case["replay"] = {
            "supported": True,
            "engine": replay.get("engine"),
            "basis": replay.get("basis"),
            "cycles": replay.get("cycles"),
            "final_seed": replay.get("final_seed"),
            "result": replay.get("result"),
            "left": replay.get("left"),
            "right": replay.get("right"),
        }

        analyst_checks = _compare_analyst_state(
            payload=selected_payload,
            replay=replay,
            rows=analyst_by_battle.get(key, []),
        )
        if analyst_checks:
            case["analyst_validation"] = analyst_checks
        for check in analyst_checks:
            status = check["status"]
            summary["analyst_checks"] += 1
            if status == "match":
                summary["analyst_matches"] += 1
            elif status == "mismatch":
                summary["analyst_mismatches"] += 1
            elif status == "not_comparable":
                summary["analyst_not_comparable"] += 1

        interesting = (
            payload_conflict
            or any(
                check["status"] in {"mismatch", "not_comparable"}
                for check in analyst_checks
            )
        )
        if args.all or interesting:
            details.append(case)

    return {
        "diagnostic": "combat_replay_regression",
        "read_only": True,
        "filters": {
            "game_id": args.game_id,
            "turn": args.turn,
            "include_all_details": bool(args.all),
        },
        "summary": summary,
        "games": by_game,
        "details": details,
        "notes": [
            "A supported replay is deterministic derived evidence, not a factual observation.",
            "Missing analyst-confirmed state is not treated as a failure.",
            "Payload conflicts are reported, never auto-reconciled.",
            "Unsupported VCRs fail closed with the exact replay reason.",
        ],
    }


def main() -> None:
    payload = run(parse_args())
    json.dump(
        payload,
        sys.stdout,
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
