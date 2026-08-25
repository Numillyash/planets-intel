from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.vcr_replay import ReplayUnsupported
from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog


CARRY_FIELDS = (
    ("damage", "damage"),
    ("crew", "crew"),
    ("torpedoes", "torpedos"),
    ("fighters", "fighters"),
)
SAMPLE_LIMIT = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only regression diagnostic for real same-turn multi-VCR ship chains. "
            "It compares deterministic terminal state from one factual VCR with the "
            "factual combat-start state of the same ship in its next VCR."
        )
    )
    parser.add_argument(
        "--game-id",
        type=int,
        default=None,
        help="Restrict the diagnostic to one game.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include every comparable transition instead of mismatches plus samples.",
    )
    return parser.parse_args()


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


def _expected_next_shield(
    *,
    race_id: int | None,
    terminal_shield: int | None,
    terminal_damage: int | None,
) -> int | None:
    """Mirror the current sequence-model shield carry rule.

    Race 1 is treated as a Federation-rule candidate because factual VCR payloads
    contain race identity but not the Battle Planner simulation toggle. The result
    is therefore a comparison against the current sequence model, not a claim that
    an advantage was enabled in every source game.
    """
    if terminal_shield is None or terminal_damage is None:
        return None
    shield = max(0, min(100, terminal_shield))
    damage = max(0, terminal_damage)
    if race_id != 1:
        return shield

    loss = 100 - shield
    recovered = (loss + 2) // 4
    max_shield = max(0, 100 - damage)
    return min(max_shield, shield + recovered)


def _transition_comparison(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    terminal = previous.get("terminal")
    start = current.get("start")
    if not isinstance(terminal, dict) or not isinstance(start, dict):
        return {
            "status": "not_comparable",
            "reason": "missing replay terminal or factual next start",
        }

    previous_defeated = bool(
        terminal.get("destroyed") or terminal.get("captured")
    )
    if previous_defeated:
        return {
            "status": "reappearance_after_defeat",
            "reason": "ship appears in a later VCR after replay marked it defeated",
        }

    carry: dict[str, Any] = {}
    carry_mismatches: list[str] = []
    carry_comparable = 0
    for terminal_key, start_key in CARRY_FIELDS:
        expected = terminal.get(terminal_key)
        actual = _integer(start, start_key)
        comparable = (
            isinstance(expected, int)
            and not isinstance(expected, bool)
            and actual is not None
        )
        if comparable:
            carry_comparable += 1
            matches = expected == actual
            if not matches:
                carry_mismatches.append(terminal_key)
        else:
            matches = None
        carry[terminal_key] = {
            "terminal": expected if isinstance(expected, int) else None,
            "next_start": actual,
            "matches": matches,
        }

    race_id = previous.get("race_id")
    terminal_shield = terminal.get("shield")
    terminal_damage = terminal.get("damage")
    expected_shield = _expected_next_shield(
        race_id=race_id if isinstance(race_id, int) else None,
        terminal_shield=(
            terminal_shield
            if isinstance(terminal_shield, int) and not isinstance(terminal_shield, bool)
            else None
        ),
        terminal_damage=(
            terminal_damage
            if isinstance(terminal_damage, int) and not isinstance(terminal_damage, bool)
            else None
        ),
    )
    actual_shield = _integer(start, "shield")
    shield_comparable = expected_shield is not None and actual_shield is not None
    shield_matches = (
        expected_shield == actual_shield if shield_comparable else None
    )

    status = "match"
    if carry_mismatches or shield_matches is False:
        status = "mismatch"
    elif carry_comparable == 0 and not shield_comparable:
        status = "not_comparable"

    return {
        "status": status,
        "carry": carry,
        "carry_comparable_fields": carry_comparable,
        "carry_mismatches": carry_mismatches,
        "shield": {
            "terminal": (
                terminal_shield
                if isinstance(terminal_shield, int) and not isinstance(terminal_shield, bool)
                else None
            ),
            "expected_next_start_by_current_sequence_rule": expected_shield,
            "next_start": actual_shield,
            "matches": shield_matches,
            "federation_race_rule_candidate": race_id == 1,
        },
    }


def _same_location(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    previous_position = previous.get("position")
    current_position = current.get("position")
    if not isinstance(previous_position, list) or not isinstance(current_position, list):
        return False
    if len(previous_position) != 2 or len(current_position) != 2:
        return False
    if any(value is None for value in previous_position + current_position):
        return False
    return previous_position == current_position


def _appearance(
    *,
    game_id: int,
    turn: int,
    vcr_id: int,
    position: list[int | None],
    side_name: str,
    raw_side: dict[str, Any],
    replay_side: dict[str, Any],
) -> dict[str, Any] | None:
    hull_id = _integer(raw_side, "hullid")
    ship_id = _integer(raw_side, "objectid")
    if hull_id is None or hull_id <= 0 or ship_id is None:
        return None
    return {
        "game_id": game_id,
        "turn": turn,
        "vcr_id": vcr_id,
        "position": position,
        "side": side_name,
        "ship_id": ship_id,
        "name": _text(raw_side, "name"),
        "hull_id": hull_id,
        "race_id": _integer(raw_side, "raceid"),
        "start": dict(raw_side),
        "terminal": dict(replay_side),
    }


def _transition_record(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    comparison = _transition_comparison(previous, current)
    return {
        "game_id": previous["game_id"],
        "turn": previous["turn"],
        "ship_id": previous["ship_id"],
        "name": previous.get("name") or current.get("name"),
        "race_id": previous.get("race_id"),
        "position": previous.get("position"),
        "from_vcr": previous["vcr_id"],
        "from_side": previous["side"],
        "to_vcr": current["vcr_id"],
        "to_side": current["side"],
        "comparison": comparison,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    with SessionLocal() as session:
        query = (
            select(CombatObservation, PrivateObservationBatch)
            .join(
                PrivateObservationBatch,
                PrivateObservationBatch.id == CombatObservation.batch_id,
            )
        )
        if args.game_id is not None:
            query = query.where(PrivateObservationBatch.game_id == args.game_id)
        query = query.order_by(
            PrivateObservationBatch.game_id,
            CombatObservation.battle_turn,
            CombatObservation.vcr_id,
            PrivateObservationBatch.observed_at.desc(),
            PrivateObservationBatch.id.desc(),
        )
        rows = session.execute(query).all()
        game_ids = sorted({int(batch.game_id) for _combat, batch in rows})
        catalogs = (
            {
                int(catalog.game_id): catalog
                for catalog in session.execute(
                    select(GameRuleCatalog).where(GameRuleCatalog.game_id.in_(game_ids))
                ).scalars().all()
            }
            if game_ids
            else {}
        )

    grouped: dict[
        tuple[int, int, int],
        list[tuple[CombatObservation, PrivateObservationBatch]],
    ] = defaultdict(list)
    for combat, batch in rows:
        grouped[
            (int(batch.game_id), int(combat.battle_turn), int(combat.vcr_id))
        ].append((combat, batch))

    appearances: list[dict[str, Any]] = []
    replay_supported = 0
    replay_unsupported = 0
    catalog_missing = 0

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
            replay_unsupported += 1
            continue
        replay_supported += 1

        position = [combat.x, combat.y]
        for side_name in ("left", "right"):
            raw_side = payload.get(side_name)
            replay_side = replay.get(side_name)
            if not isinstance(raw_side, dict) or not isinstance(replay_side, dict):
                continue
            appearance = _appearance(
                game_id=game_id,
                turn=turn,
                vcr_id=vcr_id,
                position=position,
                side_name=side_name,
                raw_side=raw_side,
                replay_side=replay_side,
            )
            if appearance is not None:
                appearances.append(appearance)

    by_ship_turn: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for appearance in appearances:
        by_ship_turn[
            (
                appearance["game_id"],
                appearance["turn"],
                appearance["ship_id"],
            )
        ].append(appearance)

    transitions: list[dict[str, Any]] = []
    skipped_location_change = 0
    candidate_chains = 0
    for chain in by_ship_turn.values():
        chain.sort(key=lambda item: item["vcr_id"])
        if len(chain) < 2:
            continue
        candidate_chains += 1
        for previous, current in zip(chain, chain[1:]):
            if not _same_location(previous, current):
                skipped_location_change += 1
                continue
            transitions.append(_transition_record(previous, current))

    summary = {
        "stored_observations": len(rows),
        "unique_vcrs": len(grouped),
        "catalog_missing": catalog_missing,
        "replay_supported": replay_supported,
        "replay_unsupported": replay_unsupported,
        "ship_appearances": len(appearances),
        "candidate_same_turn_ship_chains": candidate_chains,
        "same_location_transitions": len(transitions),
        "skipped_location_change": skipped_location_change,
        "matches": 0,
        "mismatches": 0,
        "not_comparable": 0,
        "reappearance_after_defeat": 0,
        "federation_race_transitions": 0,
        "federation_shield_rule_matches": 0,
        "federation_shield_rule_mismatches": 0,
        "non_federation_shield_rule_matches": 0,
        "non_federation_shield_rule_mismatches": 0,
    }

    mismatch_details: list[dict[str, Any]] = []
    match_samples: list[dict[str, Any]] = []
    federation_samples: list[dict[str, Any]] = []

    for transition in transitions:
        comparison = transition["comparison"]
        status = comparison["status"]
        if status in summary:
            summary[status] += 1
        if status in {"mismatch", "reappearance_after_defeat"}:
            mismatch_details.append(transition)
        elif status == "match" and len(match_samples) < SAMPLE_LIMIT:
            match_samples.append(transition)

        shield = comparison.get("shield")
        if not isinstance(shield, dict):
            continue
        shield_matches = shield.get("matches")
        is_federation = bool(shield.get("federation_race_rule_candidate"))
        if is_federation:
            summary["federation_race_transitions"] += 1
            if len(federation_samples) < SAMPLE_LIMIT:
                federation_samples.append(transition)
            if shield_matches is True:
                summary["federation_shield_rule_matches"] += 1
            elif shield_matches is False:
                summary["federation_shield_rule_mismatches"] += 1
        else:
            if shield_matches is True:
                summary["non_federation_shield_rule_matches"] += 1
            elif shield_matches is False:
                summary["non_federation_shield_rule_mismatches"] += 1

    details = transitions if args.all else mismatch_details
    return {
        "diagnostic": "combat_chain_regression",
        "read_only": True,
        "filters": {
            "game_id": args.game_id,
            "include_all_details": bool(args.all),
        },
        "summary": summary,
        "details": details,
        "match_samples": match_samples,
        "federation_samples": federation_samples,
        "notes": [
            "Only repeated appearances of the same ship in the same game, turn and factual position are compared.",
            "Damage, crew, torpedoes and fighters are expected to carry exactly between consecutive combats for a surviving ship.",
            "Shield comparison mirrors the current Battle Planner sequence rule; race 1 is only a Federation-rule candidate because the factual VCR does not encode the planner toggle.",
            "A mismatch is evidence for investigation, not automatic proof that the Host or simulator is wrong.",
            "No factual observations are modified.",
        ],
    }


def main() -> None:
    json.dump(run(parse_args()), sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
