from __future__ import annotations

import json
import sys
from typing import Any, Mapping

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.private_observation_batch import PrivateObservationBatch
from app.scripts.combat_lizard_rule_sensitivity import (
    _neutralize_lizard_identity,
    _sensitivity,
)
from app.services.vcr_replay import ReplayUnsupported
from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog


# These are derived regression baselines over factual stored VCR inputs. They
# are intentionally keyed by factual game/turn/VCR ids instead of by aggregate
# corpus counts, so additional future combats do not invalidate the check.
# VCR 201 has an extra factual anchor: its surviving Virgo terminal state was
# observed as the next VCR's combat-start state in combat_chain_regression.
BASELINES: tuple[dict[str, Any], ...] = (
    {
        "game_id": 680933,
        "turn": 42,
        "vcr_id": 201,
        "label": "T-Rex vs Virgo; survivor state anchored by VCR 202",
        "expected": {
            "sensitive": True,
            "outcome_changed": False,
            "factual_result": ["left_destroyed"],
            "neutral_result": ["left_destroyed"],
            "factual_right": {
                "shield": 0,
                "damage": 12,
                "crew": 1724,
                "fighters": 39,
                "survived": True,
            },
            "neutral_right": {
                "shield": 0,
                "damage": 9,
                "crew": 1732,
                "fighters": 42,
                "survived": True,
            },
        },
    },
    {
        "game_id": 680933,
        "turn": 43,
        "vcr_id": 216,
        "label": "Virgo vs T-Rex; Lizard on right side",
        "expected": {
            "sensitive": True,
            "outcome_changed": False,
            "factual_result": ["right_destroyed"],
            "neutral_result": ["right_destroyed"],
            "factual_left": {
                "damage": 6,
                "fighters": 68,
                "survived": True,
            },
            "neutral_left": {
                "damage": 4,
                "fighters": 71,
                "survived": True,
            },
        },
    },
)


def _subset_matches(actual: Mapping[str, Any] | None, expected: Mapping[str, Any]) -> bool:
    if actual is None:
        return False
    return all(actual.get(key) == value for key, value in expected.items())


def _latest_observation(
    rows: list[tuple[CombatObservation, PrivateObservationBatch]],
) -> CombatObservation | None:
    if not rows:
        return None
    rows.sort(
        key=lambda pair: (
            pair[1].observed_at,
            pair[1].id,
        ),
        reverse=True,
    )
    return rows[0][0]


def _evaluate_expected(
    comparison: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if bool(comparison.get("sensitive")) != bool(expected.get("sensitive")):
        errors.append("sensitive")
    if bool(comparison.get("outcome_changed")) != bool(expected.get("outcome_changed")):
        errors.append("outcome_changed")

    factual = comparison.get("factual")
    neutral = comparison.get("neutralized_lizard")
    factual_map = factual if isinstance(factual, Mapping) else {}
    neutral_map = neutral if isinstance(neutral, Mapping) else {}

    if factual_map.get("result") != expected.get("factual_result"):
        errors.append("factual_result")
    if neutral_map.get("result") != expected.get("neutral_result"):
        errors.append("neutral_result")

    for side_name in ("left", "right"):
        expected_factual = expected.get(f"factual_{side_name}")
        if isinstance(expected_factual, Mapping):
            factual_side = factual_map.get(side_name)
            if not _subset_matches(
                factual_side if isinstance(factual_side, Mapping) else None,
                expected_factual,
            ):
                errors.append(f"factual_{side_name}")

        expected_neutral = expected.get(f"neutral_{side_name}")
        if isinstance(expected_neutral, Mapping):
            neutral_side = neutral_map.get(side_name)
            if not _subset_matches(
                neutral_side if isinstance(neutral_side, Mapping) else None,
                expected_neutral,
            ):
                errors.append(f"neutral_{side_name}")

    return errors


def run() -> dict[str, Any]:
    game_ids = sorted({int(item["game_id"]) for item in BASELINES})
    with SessionLocal() as session:
        catalogs = {
            int(catalog.game_id): catalog
            for catalog in session.execute(
                select(GameRuleCatalog).where(GameRuleCatalog.game_id.in_(game_ids))
            ).scalars().all()
        }

        rows_by_key: dict[
            tuple[int, int, int],
            list[tuple[CombatObservation, PrivateObservationBatch]],
        ] = {}
        for baseline in BASELINES:
            key = (
                int(baseline["game_id"]),
                int(baseline["turn"]),
                int(baseline["vcr_id"]),
            )
            rows_by_key[key] = list(
                session.execute(
                    select(CombatObservation, PrivateObservationBatch)
                    .join(
                        PrivateObservationBatch,
                        PrivateObservationBatch.id == CombatObservation.batch_id,
                    )
                    .where(
                        PrivateObservationBatch.game_id == key[0],
                        CombatObservation.battle_turn == key[1],
                        CombatObservation.vcr_id == key[2],
                    )
                ).all()
            )

    summary = {
        "baselines": len(BASELINES),
        "matched": 0,
        "mismatched": 0,
        "missing": 0,
        "catalog_missing": 0,
        "unsupported": 0,
    }
    cases: list[dict[str, Any]] = []

    for baseline in BASELINES:
        game_id = int(baseline["game_id"])
        turn = int(baseline["turn"])
        vcr_id = int(baseline["vcr_id"])
        key = (game_id, turn, vcr_id)
        case: dict[str, Any] = {
            "game_id": game_id,
            "turn": turn,
            "vcr_id": vcr_id,
            "label": baseline["label"],
        }

        combat = _latest_observation(rows_by_key.get(key, []))
        if combat is None:
            summary["missing"] += 1
            case["status"] = "missing"
            cases.append(case)
            continue

        catalog = catalogs.get(game_id)
        if catalog is None:
            summary["catalog_missing"] += 1
            case["status"] = "catalog_missing"
            cases.append(case)
            continue

        payload = dict(combat.payload) if isinstance(combat.payload, dict) else {}
        try:
            factual = replay_nuhost_from_nu_catalog(
                payload,
                beams=list(catalog.beams),
                torpedoes=list(catalog.torpedos),
                settings=dict(catalog.settings),
            )
            neutral = replay_nuhost_from_nu_catalog(
                _neutralize_lizard_identity(payload),
                beams=list(catalog.beams),
                torpedoes=list(catalog.torpedos),
                settings=dict(catalog.settings),
            )
        except ReplayUnsupported as exc:
            summary["unsupported"] += 1
            case["status"] = "unsupported"
            case["reason"] = str(exc)
            cases.append(case)
            continue

        comparison = _sensitivity(factual, neutral)
        errors = _evaluate_expected(comparison, baseline["expected"])
        case["status"] = "match" if not errors else "mismatch"
        case["errors"] = errors
        case["sensitivity"] = comparison
        if errors:
            summary["mismatched"] += 1
        else:
            summary["matched"] += 1
        cases.append(case)

    return {
        "diagnostic": "combat_lizard_regression",
        "read_only": True,
        "summary": summary,
        "cases": cases,
        "notes": [
            "Baselines are derived replay regression expectations over factual stored VCR inputs; they do not create new factual observations.",
            "VCR 201 additionally anchors the factual surviving Virgo terminal state to the next observed VCR combat-start state.",
            "New unrelated VCRs do not affect these keyed baselines.",
        ],
    }


def main() -> None:
    result = run()
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")
    summary = result["summary"]
    if summary["mismatched"] or summary["missing"] or summary["catalog_missing"] or summary["unsupported"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
