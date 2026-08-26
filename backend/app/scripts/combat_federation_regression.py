from __future__ import annotations

import json
import sys
from typing import Any, Mapping

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.private_observation_batch import PrivateObservationBatch


BASELINE = {
    "game_id": 683230,
    "turn": 15,
    "vcr_id": 20,
    "ship_id": 54,
    "hull_id": 19,
    "label": "Federation Kittyhawk +3 fighter bays",
    "expected_hull_bays": 6,
    "expected_vcr_bays": 9,
}


def _integer(record: Mapping[str, Any] | None, key: str) -> int | None:
    if not isinstance(record, Mapping):
        return None
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _hull_bays(catalog: GameRuleCatalog, hull_id: int) -> int | None:
    for hull in catalog.hulls:
        if not isinstance(hull, Mapping) or _integer(hull, "id") != hull_id:
            continue
        for key in ("fighterbays", "bays", "baycount"):
            value = _integer(hull, key)
            if value is not None:
                return value
    return None


def _latest_observation(
    rows: list[tuple[CombatObservation, PrivateObservationBatch]],
) -> CombatObservation | None:
    if not rows:
        return None
    rows.sort(
        key=lambda pair: (pair[1].observed_at, pair[1].id),
        reverse=True,
    )
    return rows[0][0]


def run() -> dict[str, Any]:
    game_id = int(BASELINE["game_id"])
    turn = int(BASELINE["turn"])
    vcr_id = int(BASELINE["vcr_id"])
    with SessionLocal() as session:
        catalog = session.execute(
            select(GameRuleCatalog).where(GameRuleCatalog.game_id == game_id)
        ).scalar_one_or_none()
        rows = list(
            session.execute(
                select(CombatObservation, PrivateObservationBatch)
                .join(
                    PrivateObservationBatch,
                    PrivateObservationBatch.id == CombatObservation.batch_id,
                )
                .where(
                    PrivateObservationBatch.game_id == game_id,
                    CombatObservation.battle_turn == turn,
                    CombatObservation.vcr_id == vcr_id,
                )
            ).all()
        )

    case: dict[str, Any] = {
        "game_id": game_id,
        "turn": turn,
        "vcr_id": vcr_id,
        "label": BASELINE["label"],
    }
    if catalog is None:
        case["status"] = "catalog_missing"
        return {
            "diagnostic": "combat_federation_regression",
            "read_only": True,
            "summary": {"baselines": 1, "matched": 0, "failed": 1},
            "cases": [case],
        }

    combat = _latest_observation(rows)
    if combat is None:
        case["status"] = "missing"
        return {
            "diagnostic": "combat_federation_regression",
            "read_only": True,
            "summary": {"baselines": 1, "matched": 0, "failed": 1},
            "cases": [case],
        }

    payload = dict(combat.payload) if isinstance(combat.payload, dict) else {}
    matched_side: Mapping[str, Any] | None = None
    matched_side_name: str | None = None
    for side_name in ("left", "right"):
        side = payload.get(side_name)
        if not isinstance(side, Mapping):
            continue
        if (
            _integer(side, "objectid") == int(BASELINE["ship_id"])
            and _integer(side, "hullid") == int(BASELINE["hull_id"])
            and _integer(side, "raceid") == 1
        ):
            matched_side = side
            matched_side_name = side_name
            break

    errors: list[str] = []
    if matched_side is None:
        errors.append("federation_ship_side")
        hull_bays = _hull_bays(catalog, int(BASELINE["hull_id"]))
        vcr_bays = None
    else:
        hull_bays = _hull_bays(catalog, int(BASELINE["hull_id"]))
        vcr_bays = _integer(matched_side, "baycount")
        if hull_bays != int(BASELINE["expected_hull_bays"]):
            errors.append("catalog_hull_bays")
        if vcr_bays != int(BASELINE["expected_vcr_bays"]):
            errors.append("vcr_bays")
        if hull_bays is not None and vcr_bays is not None and vcr_bays - hull_bays != 3:
            errors.append("fed_bay_delta")

    case.update(
        {
            "status": "match" if not errors else "mismatch",
            "errors": errors,
            "side": matched_side_name,
            "hull_bays": hull_bays,
            "vcr_bays": vcr_bays,
            "delta": None if hull_bays is None or vcr_bays is None else vcr_bays - hull_bays,
        }
    )
    return {
        "diagnostic": "combat_federation_regression",
        "read_only": True,
        "summary": {
            "baselines": 1,
            "matched": 0 if errors else 1,
            "failed": 1 if errors else 0,
        },
        "cases": [case],
        "notes": [
            "This keyed baseline protects the directly observed Federation +3 carrier-bay transformation.",
            "It does not claim validation of damaged-start weapon continuity or between-fight shield recovery; the current factual corpus contains no isolating cases for those branches.",
        ],
    }


def main() -> None:
    result = run()
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")
    if result["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
