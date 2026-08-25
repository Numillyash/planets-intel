from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from typing import Any, Mapping

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.vcr_replay import ReplayUnsupported
from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog


SAMPLE_LIMIT = 10
TERMINAL_FIELDS = (
    "shield",
    "damage",
    "crew",
    "torpedoes",
    "fighters",
    "destroyed",
    "captured",
    "survived",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only differential diagnostic for factual Lizard VCRs. Each factual "
            "race-2 replay is compared with a counterfactual replay that neutralizes "
            "only the Lizard 150% in-combat damage-limit identity. A sensitive case "
            "means the special rule materially changes deterministic output; it is "
            "coverage evidence, not an independent factual validation."
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
        help="Include all factual Lizard cases instead of only sensitive samples.",
    )
    return parser.parse_args()


def _integer(record: Mapping[str, Any] | None, key: str) -> int | None:
    if not isinstance(record, Mapping):
        return None
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _text(record: Mapping[str, Any] | None, key: str) -> str | None:
    if not isinstance(record, Mapping):
        return None
    value = record.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _lizard_ship_sides(payload: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for side_name in ("left", "right"):
        side = payload.get(side_name)
        if not isinstance(side, Mapping):
            continue
        hull_id = _integer(side, "hullid")
        race_id = _integer(side, "raceid")
        if hull_id is not None and hull_id > 0 and race_id == 2:
            result.append(side_name)
    return result


def _neutralize_lizard_identity(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(payload))
    for side_name in _lizard_ship_sides(payload):
        side = result.get(side_name)
        if isinstance(side, dict):
            side["raceid"] = 0
    return result


def _terminal_projection(replay: Mapping[str, Any], side_name: str) -> dict[str, Any] | None:
    side = replay.get(side_name)
    if not isinstance(side, Mapping):
        return None
    return {key: side.get(key) for key in TERMINAL_FIELDS}


def _replay_projection(replay: Mapping[str, Any]) -> dict[str, Any]:
    labels = replay.get("result")
    return {
        "result": list(labels) if isinstance(labels, list) else [],
        "left": _terminal_projection(replay, "left"),
        "right": _terminal_projection(replay, "right"),
    }


def _sensitivity(
    factual: Mapping[str, Any],
    neutral: Mapping[str, Any],
) -> dict[str, Any]:
    factual_projection = _replay_projection(factual)
    neutral_projection = _replay_projection(neutral)
    outcome_changed = factual_projection["result"] != neutral_projection["result"]
    left_changed = factual_projection["left"] != neutral_projection["left"]
    right_changed = factual_projection["right"] != neutral_projection["right"]
    return {
        "sensitive": outcome_changed or left_changed or right_changed,
        "outcome_changed": outcome_changed,
        "left_terminal_changed": left_changed,
        "right_terminal_changed": right_changed,
        "factual": factual_projection,
        "neutralized_lizard": neutral_projection,
    }


def _case_record(
    *,
    game_id: int,
    turn: int,
    vcr_id: int,
    payload: Mapping[str, Any],
    sensitivity: Mapping[str, Any],
) -> dict[str, Any]:
    left = payload.get("left")
    right = payload.get("right")
    left_hull = _integer(left if isinstance(left, Mapping) else None, "hullid")
    right_hull = _integer(right if isinstance(right, Mapping) else None, "hullid")
    shape = "ship_vs_planet" if (right_hull is not None and right_hull <= 0) else "ship_vs_ship"
    return {
        "game_id": game_id,
        "turn": turn,
        "vcr_id": vcr_id,
        "shape": shape,
        "lizard_sides": _lizard_ship_sides(payload),
        "left": {
            "object_id": _integer(left if isinstance(left, Mapping) else None, "objectid"),
            "name": _text(left if isinstance(left, Mapping) else None, "name"),
            "hull_id": left_hull,
            "race_id": _integer(left if isinstance(left, Mapping) else None, "raceid"),
            "start_damage": _integer(left if isinstance(left, Mapping) else None, "damage"),
        },
        "right": {
            "object_id": _integer(right if isinstance(right, Mapping) else None, "objectid"),
            "name": _text(right if isinstance(right, Mapping) else None, "name"),
            "hull_id": right_hull,
            "race_id": _integer(right if isinstance(right, Mapping) else None, "raceid"),
            "start_damage": _integer(right if isinstance(right, Mapping) else None, "damage"),
        },
        "sensitivity": dict(sensitivity),
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

    grouped: dict[tuple[int, int, int], tuple[CombatObservation, PrivateObservationBatch]] = {}
    for combat, batch in rows:
        key = (int(batch.game_id), int(combat.battle_turn), int(combat.vcr_id))
        grouped.setdefault(key, (combat, batch))

    summary = {
        "stored_observations": len(rows),
        "unique_vcrs": len(grouped),
        "lizard_vcrs": 0,
        "lizard_ship_side_appearances": 0,
        "ship_vs_ship_lizard_vcrs": 0,
        "ship_vs_planet_lizard_vcrs": 0,
        "catalog_missing": 0,
        "factual_replay_unsupported": 0,
        "neutral_replay_unsupported": 0,
        "comparable": 0,
        "sensitive": 0,
        "insensitive": 0,
        "outcome_changed": 0,
        "terminal_only_changed": 0,
        "ship_vs_ship_sensitive": 0,
        "ship_vs_planet_sensitive": 0,
    }
    sensitive_cases: list[dict[str, Any]] = []
    all_cases: list[dict[str, Any]] = []

    for (game_id, turn, vcr_id), (combat, _batch) in sorted(grouped.items()):
        payload = dict(combat.payload) if isinstance(combat.payload, dict) else {}
        lizard_sides = _lizard_ship_sides(payload)
        if not lizard_sides:
            continue
        summary["lizard_vcrs"] += 1
        summary["lizard_ship_side_appearances"] += len(lizard_sides)

        right = payload.get("right")
        right_hull = _integer(right if isinstance(right, Mapping) else None, "hullid")
        shape = "ship_vs_planet" if (right_hull is not None and right_hull <= 0) else "ship_vs_ship"
        summary[f"{shape}_lizard_vcrs"] += 1

        catalog = catalogs.get(game_id)
        if catalog is None:
            summary["catalog_missing"] += 1
            continue

        try:
            factual = replay_nuhost_from_nu_catalog(
                payload,
                beams=list(catalog.beams),
                torpedoes=list(catalog.torpedos),
                settings=dict(catalog.settings),
            )
        except ReplayUnsupported:
            summary["factual_replay_unsupported"] += 1
            continue

        neutral_payload = _neutralize_lizard_identity(payload)
        try:
            neutral = replay_nuhost_from_nu_catalog(
                neutral_payload,
                beams=list(catalog.beams),
                torpedoes=list(catalog.torpedos),
                settings=dict(catalog.settings),
            )
        except ReplayUnsupported:
            summary["neutral_replay_unsupported"] += 1
            continue

        comparison = _sensitivity(factual, neutral)
        summary["comparable"] += 1
        if comparison["sensitive"]:
            summary["sensitive"] += 1
            summary[f"{shape}_sensitive"] += 1
            if comparison["outcome_changed"]:
                summary["outcome_changed"] += 1
            else:
                summary["terminal_only_changed"] += 1
        else:
            summary["insensitive"] += 1

        record = _case_record(
            game_id=game_id,
            turn=turn,
            vcr_id=vcr_id,
            payload=payload,
            sensitivity=comparison,
        )
        if args.all:
            all_cases.append(record)
        elif comparison["sensitive"] and len(sensitive_cases) < SAMPLE_LIMIT:
            sensitive_cases.append(record)

    return {
        "diagnostic": "combat_lizard_rule_sensitivity",
        "read_only": True,
        "counterfactual": "race-2 ship identity neutralized to raceid=0 only",
        "filters": {
            "game_id": args.game_id,
            "include_all_cases": bool(args.all),
        },
        "summary": summary,
        "cases": all_cases if args.all else sensitive_cases,
        "notes": [
            "A sensitive case means the Lizard 150% in-combat endurance branch changes deterministic output for the same factual seed/input.",
            "This is branch-exercise evidence, not an independent factual confirmation of the Host rule.",
            "All non-race VCR fields and the persisted game rule catalog remain unchanged in the counterfactual replay.",
            "Planet combat keeps the factual NuHost post-combat destruction semantics; only the in-combat race-2 endurance identity is neutralized for comparison.",
            "No factual observations are modified.",
        ],
    }


def main() -> None:
    json.dump(run(parse_args()), sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
