from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Mapping

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation


RIGHT_BALANCE_MASS_BONUS = 360
MIN_RIGHT_PHYSICAL_MASS = 140


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only evidence audit for the Host right-side balance mass bonus. "
            "The audit only treats a case as isolating when the factual VCR has a "
            "carrier on LEFT, a ship on RIGHT with no fighter bays/torpedo launchers, "
            "and a next-turn same-position private ship observation. Owner-observed "
            "post-Host mass is the exact comparison tier; foreign observations are "
            "reported separately as supporting evidence only."
        )
    )
    parser.add_argument("--game-id", type=int, default=None)
    return parser.parse_args()


def _integer(record: Mapping[str, Any] | None, key: str) -> int | None:
    if not isinstance(record, Mapping):
        return None
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _positive_integer(record: Mapping[str, Any] | None, key: str) -> int | None:
    value = _integer(record, key)
    return value if value is not None and value > 0 else None


def _side(payload: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    value = payload.get(name)
    return value if isinstance(value, Mapping) else None


def _candidate_shape(payload: Mapping[str, Any]) -> bool:
    left = _side(payload, "left")
    right = _side(payload, "right")
    if left is None or right is None:
        return False
    left_hull = _positive_integer(left, "hullid")
    right_hull = _positive_integer(right, "hullid")
    left_bays = _integer(left, "baycount")
    right_mass = _positive_integer(right, "mass")
    return (
        left_hull is not None
        and right_hull is not None
        and left_bays is not None
        and left_bays > 0
        and right_mass is not None
    )


def _ammo_mass_isolated(payload: Mapping[str, Any]) -> bool:
    right = _side(payload, "right")
    if right is None:
        return False
    launchers = _integer(right, "launchercount")
    bays = _integer(right, "baycount")
    return launchers == 0 and bays == 0


def _classify_delta(
    *,
    vcr_mass: int,
    observed_mass: int,
    owner_observed: bool,
) -> str:
    delta = vcr_mass - observed_mass
    tier = "exact" if owner_observed else "supporting"
    if delta == RIGHT_BALANCE_MASS_BONUS:
        return f"{tier}_bonus_applied"
    if delta == 0:
        return f"{tier}_bonus_not_applied"
    return f"{tier}_other_delta"


def _latest_combat_rows(
    rows: list[tuple[CombatObservation, PrivateObservationBatch]],
) -> dict[tuple[int, int, int], tuple[CombatObservation, PrivateObservationBatch]]:
    result: dict[tuple[int, int, int], tuple[CombatObservation, PrivateObservationBatch]] = {}
    ordered = sorted(
        rows,
        key=lambda pair: (
            int(pair[1].game_id),
            int(pair[0].battle_turn),
            int(pair[0].vcr_id),
            pair[1].observed_at,
            pair[1].id,
        ),
        reverse=True,
    )
    for combat, batch in ordered:
        key = (int(batch.game_id), int(combat.battle_turn), int(combat.vcr_id))
        result.setdefault(key, (combat, batch))
    return result


def _matching_ship_observations(
    rows: list[tuple[ShipObservation, PrivateObservationBatch]],
    *,
    game_id: int,
    turn: int,
    ship_id: int,
    owner_id: int | None,
    hull_id: int,
    x: int | None,
    y: int | None,
) -> list[tuple[ShipObservation, PrivateObservationBatch, int]]:
    result: list[tuple[ShipObservation, PrivateObservationBatch, int]] = []
    for ship, batch in rows:
        if int(batch.game_id) != game_id or int(batch.turn) != turn:
            continue
        if int(ship.ship_id) != ship_id:
            continue
        if ship.hull_id is not None and int(ship.hull_id) != hull_id:
            continue
        if owner_id is not None and ship.owner_id is not None and int(ship.owner_id) != owner_id:
            continue
        if x is not None and ship.x is not None and int(ship.x) != x:
            continue
        if y is not None and ship.y is not None and int(ship.y) != y:
            continue
        payload = dict(ship.payload) if isinstance(ship.payload, dict) else {}
        observed_mass = _positive_integer(payload, "mass")
        if observed_mass is None:
            continue
        result.append((ship, batch, observed_mass))
    result.sort(
        key=lambda item: (
            item[1].source_player_slot_id == owner_id if owner_id is not None else False,
            item[1].observed_at,
            item[1].id,
        ),
        reverse=True,
    )
    return result


def run(args: argparse.Namespace) -> dict[str, Any]:
    with SessionLocal() as session:
        combat_query = select(CombatObservation, PrivateObservationBatch).join(
            PrivateObservationBatch,
            PrivateObservationBatch.id == CombatObservation.batch_id,
        )
        ship_query = select(ShipObservation, PrivateObservationBatch).join(
            PrivateObservationBatch,
            PrivateObservationBatch.id == ShipObservation.batch_id,
        )
        if args.game_id is not None:
            combat_query = combat_query.where(PrivateObservationBatch.game_id == args.game_id)
            ship_query = ship_query.where(PrivateObservationBatch.game_id == args.game_id)
        combat_rows = list(session.execute(combat_query).all())
        ship_rows = list(session.execute(ship_query).all())

    unique_combats = _latest_combat_rows(combat_rows)
    summary = {
        "stored_combat_observations": len(combat_rows),
        "unique_vcrs": len(unique_combats),
        "candidate_shapes": 0,
        "ammo_mass_isolating_shapes": 0,
        "next_turn_same_position_mass_observed": 0,
        "owner_observed_exact_cases": 0,
        "foreign_observed_supporting_cases": 0,
        "exact_bonus_applied": 0,
        "exact_bonus_not_applied": 0,
        "exact_other_delta": 0,
        "supporting_bonus_applied": 0,
        "supporting_bonus_not_applied": 0,
        "supporting_other_delta": 0,
        "excluded_federation_right_mass_bonus": 0,
        "excluded_below_physical_mass_threshold": 0,
    }
    cases: list[dict[str, Any]] = []

    for (game_id, turn, vcr_id), (combat, _batch) in sorted(unique_combats.items()):
        payload = dict(combat.payload) if isinstance(combat.payload, dict) else {}
        if not _candidate_shape(payload):
            continue
        summary["candidate_shapes"] += 1
        if not _ammo_mass_isolated(payload):
            continue
        summary["ammo_mass_isolating_shapes"] += 1

        right = _side(payload, "right")
        if right is None:
            continue
        right_race = _integer(right, "raceid")
        if right_race == 1:
            summary["excluded_federation_right_mass_bonus"] += 1
            continue

        ship_id = _positive_integer(right, "objectid")
        hull_id = _positive_integer(right, "hullid")
        vcr_mass = _positive_integer(right, "mass")
        owner_id = _integer(right, "raceid")  # placeholder overwritten below
        owner_id = _integer(payload, "rightownerid")
        if ship_id is None or hull_id is None or vcr_mass is None:
            continue

        matches = _matching_ship_observations(
            ship_rows,
            game_id=game_id,
            turn=turn + 1,
            ship_id=ship_id,
            owner_id=owner_id,
            hull_id=hull_id,
            x=combat.x,
            y=combat.y,
        )
        if not matches:
            continue
        ship, batch, observed_mass = matches[0]
        summary["next_turn_same_position_mass_observed"] += 1

        if observed_mass < MIN_RIGHT_PHYSICAL_MASS:
            summary["excluded_below_physical_mass_threshold"] += 1
            cases.append(
                {
                    "game_id": game_id,
                    "turn": turn,
                    "vcr_id": vcr_id,
                    "right_ship_id": ship_id,
                    "status": "not_comparable_below_physical_mass_threshold",
                    "vcr_mass": vcr_mass,
                    "next_turn_mass": observed_mass,
                    "next_turn": turn + 1,
                }
            )
            continue

        owner_observed = owner_id is not None and int(batch.source_player_slot_id) == owner_id
        status = _classify_delta(
            vcr_mass=vcr_mass,
            observed_mass=observed_mass,
            owner_observed=owner_observed,
        )
        summary[status] += 1
        if owner_observed:
            summary["owner_observed_exact_cases"] += 1
        else:
            summary["foreign_observed_supporting_cases"] += 1

        cases.append(
            {
                "game_id": game_id,
                "turn": turn,
                "vcr_id": vcr_id,
                "position": [combat.x, combat.y],
                "left": {
                    "ship_id": _positive_integer(_side(payload, "left"), "objectid"),
                    "bay_count": _integer(_side(payload, "left"), "baycount"),
                },
                "right": {
                    "ship_id": ship_id,
                    "owner_id": owner_id,
                    "hull_id": hull_id,
                    "race_id": right_race,
                    "launcher_count": _integer(right, "launchercount"),
                    "bay_count": _integer(right, "baycount"),
                    "vcr_mass": vcr_mass,
                },
                "next_turn_observation": {
                    "turn": turn + 1,
                    "mass": observed_mass,
                    "observer_slot_id": int(batch.source_player_slot_id),
                    "owner_observed": owner_observed,
                    "x": ship.x,
                    "y": ship.y,
                },
                "mass_delta": vcr_mass - observed_mass,
                "status": status,
            }
        )

    return {
        "diagnostic": "combat_right_balance_evidence",
        "read_only": True,
        "filters": {"game_id": args.game_id},
        "summary": summary,
        "cases": cases,
        "notes": [
            "The +360 rule is never inferred from hull mass alone.",
            "Exact evidence requires a next-turn same-position owner-observed ship mass and a RIGHT ship with zero launchers and zero fighter bays, so combat ammunition consumption cannot explain the mass delta.",
            "RIGHT Federation ships are excluded because their separate +50 combat-mass advantage would confound the comparison.",
            "A +360 delta is evidence that the balance bonus was present in the factual VCR combat mass; a zero delta is evidence that it was not applied for that battle.",
            "Non-owner ship observations are reported as supporting evidence only and are not promoted to exact validation.",
            "No factual observations are modified.",
        ],
    }


def main() -> None:
    json.dump(run(parse_args()), sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
