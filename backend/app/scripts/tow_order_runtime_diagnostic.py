from __future__ import annotations

import argparse
import json
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.models.ship_order_draft import ShipOrderDraft
from app.services.movement_prediction_unified_runtime import get_draft_movement_prediction
from app.services.movement_tow import payload_integer, payload_tow_target_id


def _payload(ship: ShipObservation) -> dict[str, Any]:
    return dict(ship.payload) if isinstance(ship.payload, dict) else {}


def _payload_value(payload: dict[str, Any], *keys: str) -> Any:
    wanted = {key.casefold() for key in keys}
    for key, value in payload.items():
        if str(key).casefold() in wanted:
            return value
    return None


def _latest_batches() -> list[tuple[PrivateObservationBatch, PlanetsAccount]]:
    with SessionLocal() as session:
        rows = list(
            session.execute(
                select(PrivateObservationBatch, PlanetsAccount)
                .join(
                    PlanetsAccount,
                    PlanetsAccount.id
                    == PrivateObservationBatch.observer_planets_account_id,
                )
                .where(PlanetsAccount.is_active.is_(True))
                .order_by(
                    PrivateObservationBatch.observer_planets_account_id,
                    PrivateObservationBatch.game_id,
                    PrivateObservationBatch.turn.desc(),
                    PrivateObservationBatch.observed_at.desc(),
                    PrivateObservationBatch.id.desc(),
                )
            ).all()
        )

    latest: dict[tuple[int, int], tuple[PrivateObservationBatch, PlanetsAccount]] = {}
    for batch, account in rows:
        key = (int(batch.observer_planets_account_id), int(batch.game_id))
        if key not in latest:
            latest[key] = (batch, account)
    return list(latest.values())


def _draft_dict(draft: ShipOrderDraft | None) -> dict[str, Any] | None:
    if draft is None:
        return None
    return {
        "id": int(draft.id),
        "base_batch_id": int(draft.base_batch_id),
        "base_snapshot_hash": draft.base_snapshot_hash,
        "movement_mode": draft.movement_mode,
        "mission": draft.mission,
        "warp": draft.warp,
        "waypoint_x": draft.waypoint_x,
        "waypoint_y": draft.waypoint_y,
        "intercept_target_ship_id": draft.intercept_target_ship_id,
        "tow_target_ship_id": draft.tow_target_ship_id,
        "friendly_code": draft.friendly_code,
        "primary_enemy_id": draft.primary_enemy_id,
    }


def _ship_dict(ship: ShipObservation) -> dict[str, Any]:
    payload = _payload(ship)
    return {
        "ship_id": int(ship.ship_id),
        "name": ship.name,
        "owner_id": ship.owner_id,
        "hull_id": ship.hull_id,
        "x": ship.x,
        "y": ship.y,
        "warp_column": ship.warp,
        "payload": {
            "mission": _payload_value(payload, "mission"),
            "missionname": _payload_value(payload, "missionname", "mission_name"),
            "mission1target": _payload_value(
                payload,
                "mission1target",
                "mission1_target_id",
                "mission1targetid",
            ),
            "mission2target": _payload_value(
                payload,
                "mission2target",
                "mission2_target_id",
                "mission2targetid",
            ),
            "warp": _payload_value(payload, "warp"),
            "waypointx": _payload_value(payload, "waypointx", "targetx", "waypoint_x"),
            "waypointy": _payload_value(payload, "waypointy", "targety", "waypoint_y"),
            "neutronium": _payload_value(payload, "neutronium", "fuel"),
        },
        "parsed_mission": payload_integer(payload, "mission"),
        "parsed_mission1target": payload_tow_target_id(payload),
    }


def run(ship_ids: set[int]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "requested_ship_ids": sorted(ship_ids),
        "matches": [],
    }

    for batch, account in _latest_batches():
        with SessionLocal() as session:
            ships = list(
                session.execute(
                    select(ShipObservation).where(
                        ShipObservation.batch_id == batch.id,
                        ShipObservation.ship_id.in_(sorted(ship_ids)),
                    )
                ).scalars().all()
            )
            if not ships:
                continue

            drafts = list(
                session.execute(
                    select(ShipOrderDraft).where(
                        ShipOrderDraft.user_id == account.user_id,
                        ShipOrderDraft.linked_account_id == account.id,
                        ShipOrderDraft.game_id == batch.game_id,
                        ShipOrderDraft.turn == batch.turn,
                        ShipOrderDraft.ship_id.in_(sorted(ship_ids)),
                    )
                ).scalars().all()
            )
            draft_by_ship = {int(draft.ship_id): draft for draft in drafts}

        prediction_error: str | None = None
        prediction_items: list[dict[str, Any]] = []
        try:
            prediction = get_draft_movement_prediction(
                user_id=int(account.user_id),
                linked_account_id=int(account.id),
                game_id=int(batch.game_id),
                turn=int(batch.turn),
            )
            raw_items = prediction.get("items")
            if isinstance(raw_items, list):
                prediction_items = [
                    dict(item)
                    for item in raw_items
                    if isinstance(item, dict)
                    and (
                        item.get("ship_id") in ship_ids
                        or item.get("tower_ship_id") in ship_ids
                        or item.get("tow_target_ship_id") in ship_ids
                        or item.get("target_ship_id") in ship_ids
                    )
                ]
        except Exception as exc:  # diagnostic: preserve concrete runtime failure
            prediction_error = f"{type(exc).__name__}: {exc}"

        result["matches"].append(
            {
                "user_id": int(account.user_id),
                "linked_account_id": int(account.id),
                "game_id": int(batch.game_id),
                "turn": int(batch.turn),
                "batch_id": int(batch.id),
                "source_player_slot_id": int(batch.source_player_slot_id),
                "snapshot_hash": batch.snapshot_hash,
                "ships": [
                    {
                        **_ship_dict(ship),
                        "draft": _draft_dict(draft_by_ship.get(int(ship.ship_id))),
                    }
                    for ship in sorted(ships, key=lambda item: int(item.ship_id))
                ],
                "prediction_items": prediction_items,
                "prediction_error": prediction_error,
            }
        )

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect raw factual mission/target fields, local drafts and movement "
            "prediction rows for selected ship ids in every latest active snapshot."
        )
    )
    parser.add_argument(
        "ship_ids",
        nargs="+",
        type=int,
        help="Ship ids to inspect, for example: 33 79",
    )
    args = parser.parse_args()
    payload = run({int(value) for value in args.ship_ids})
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
