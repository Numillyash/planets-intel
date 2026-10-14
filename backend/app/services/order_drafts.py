from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.models.ship_order_draft import ShipOrderDraft


TOW_MISSION_NAMES = frozenset({"tow", "try to tow", "mission #6"})


class OrderDraftAccessError(Exception):
    pass


class OrderDraftNotFound(Exception):
    pass


def _payload_int(payload: dict[str, Any], *keys: str) -> int | None:
    normalized = {key.lower() for key in keys}
    for key, value in payload.items():
        if key.lower() not in normalized:
            continue
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return None
    return None


def _payload_str(payload: dict[str, Any], *keys: str) -> str | None:
    normalized = {key.lower() for key in keys}
    for key, value in payload.items():
        if key.lower() not in normalized:
            continue
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
    return None


def _is_tow_mission_name(value: str | None) -> bool:
    return value is not None and value.strip().casefold() in TOW_MISSION_NAMES


def _account(
    session: Session,
    *,
    user_id: int,
    linked_account_id: int,
) -> PlanetsAccount:
    account = session.execute(
        select(PlanetsAccount).where(
            PlanetsAccount.id == linked_account_id,
            PlanetsAccount.user_id == user_id,
            PlanetsAccount.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if account is None:
        raise OrderDraftAccessError("Linked Planets.nu account is unavailable")
    return account


def _factual_ship_context(
    session: Session,
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
    ship_id: int,
) -> tuple[PrivateObservationBatch, ShipObservation]:
    _account(
        session,
        user_id=user_id,
        linked_account_id=linked_account_id,
    )

    batch = session.execute(
        select(PrivateObservationBatch)
        .where(
            PrivateObservationBatch.game_id == game_id,
            PrivateObservationBatch.observer_planets_account_id
            == linked_account_id,
        )
        .order_by(
            PrivateObservationBatch.turn.desc(),
            PrivateObservationBatch.observed_at.desc(),
            PrivateObservationBatch.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if batch is None:
        raise OrderDraftNotFound(
            "No factual snapshot is stored for this observer and game"
        )
    if batch.turn != turn:
        raise OrderDraftAccessError(
            "Order drafts are only available for the latest factual turn"
        )

    ship = session.execute(
        select(ShipObservation).where(
            ShipObservation.batch_id == batch.id,
            ShipObservation.ship_id == ship_id,
        )
    ).scalar_one_or_none()
    if ship is None:
        raise OrderDraftNotFound("Ship is not present in the factual snapshot")

    if (
        batch.source_player_slot_id is None
        or ship.owner_id != batch.source_player_slot_id
    ):
        raise OrderDraftAccessError(
            "Order drafts are only allowed for ships controlled by the observer"
        )

    return batch, ship


def _validate_intercept_target(
    session: Session,
    *,
    batch_id: int,
    ship_id: int,
    target_ship_id: int,
) -> None:
    if target_ship_id == ship_id:
        raise OrderDraftAccessError("A ship cannot intercept itself")

    target = session.execute(
        select(ShipObservation.ship_id).where(
            ShipObservation.batch_id == batch_id,
            ShipObservation.ship_id == target_ship_id,
        )
    ).scalar_one_or_none()
    if target is None:
        raise OrderDraftAccessError(
            "Intercept target is not visible in the latest factual snapshot"
        )


def _validate_tow_target(
    session: Session,
    *,
    batch_id: int,
    ship: ShipObservation,
    target_ship_id: int,
) -> None:
    if target_ship_id == ship.ship_id:
        raise OrderDraftAccessError("A ship cannot Tow itself")

    target = session.execute(
        select(ShipObservation).where(
            ShipObservation.batch_id == batch_id,
            ShipObservation.ship_id == target_ship_id,
        )
    ).scalar_one_or_none()
    if target is None:
        raise OrderDraftAccessError(
            "Tow target is not visible in the latest factual snapshot"
        )

    if None in (ship.x, ship.y, target.x, target.y):
        raise OrderDraftAccessError(
            "Tow target colocation cannot be established from factual positions"
        )
    if (ship.x, ship.y) != (target.x, target.y):
        raise OrderDraftAccessError(
            "Tow target must be colocated with the towing ship in the latest factual snapshot"
        )


def _upstream_mission(ship: ShipObservation) -> str | None:
    named = _payload_str(ship.payload, "missionname", "mission_name")
    if named:
        return named
    mission_id = _payload_int(ship.payload, "mission")
    return f"Mission #{mission_id}" if mission_id is not None else None


def _upstream_tow_target(ship: ShipObservation) -> int | None:
    if _payload_int(ship.payload, "mission") != 6:
        return None
    target_id = _payload_int(
        ship.payload,
        "mission1target",
        "mission1_target_id",
        "mission1targetid",
    )
    return target_id if target_id is not None and target_id > 0 else None


def _serialize(
    draft: ShipOrderDraft,
    *,
    batch: PrivateObservationBatch,
    ship: ShipObservation,
) -> dict[str, Any]:
    upstream_waypoint_x = _payload_int(
        ship.payload,
        "waypointx",
        "targetx",
        "waypoint_x",
    )
    upstream_waypoint_y = _payload_int(
        ship.payload,
        "waypointy",
        "targety",
        "waypoint_y",
    )
    upstream_friendly_code = _payload_str(
        ship.payload,
        "friendlycode",
        "friendly_code",
        "fcode",
    )
    upstream_mission = _upstream_mission(ship)
    upstream_primary_enemy_id = _payload_int(
        ship.payload,
        "enemy",
        "primaryenemy",
        "primary_enemy_id",
    )
    upstream_tow_target_ship_id = _upstream_tow_target(ship)
    changed_waypoint = (
        draft.waypoint_x is not None
        and draft.waypoint_y is not None
        and (
            draft.waypoint_x != upstream_waypoint_x
            or draft.waypoint_y != upstream_waypoint_y
        )
    )

    return {
        "game_id": draft.game_id,
        "linked_account_id": draft.linked_account_id,
        "turn": draft.turn,
        "ship_id": draft.ship_id,
        "base_batch_id": draft.base_batch_id,
        "base_snapshot_hash": draft.base_snapshot_hash,
        "stale": draft.base_snapshot_hash != batch.snapshot_hash,
        "upstream_warp": ship.warp,
        "upstream_waypoint_x": upstream_waypoint_x,
        "upstream_waypoint_y": upstream_waypoint_y,
        "upstream_friendly_code": upstream_friendly_code,
        "upstream_mission": upstream_mission,
        "upstream_primary_enemy_id": upstream_primary_enemy_id,
        "upstream_tow_target_ship_id": upstream_tow_target_ship_id,
        "warp": draft.warp,
        "waypoint_x": draft.waypoint_x,
        "waypoint_y": draft.waypoint_y,
        "movement_mode": draft.movement_mode,
        "intercept_target_ship_id": draft.intercept_target_ship_id,
        "tow_target_ship_id": draft.tow_target_ship_id,
        "friendly_code": draft.friendly_code,
        "mission": draft.mission,
        "primary_enemy_id": draft.primary_enemy_id,
        "changed_warp": draft.warp is not None and draft.warp != ship.warp,
        "changed_waypoint": changed_waypoint,
        "changed_movement": draft.movement_mode == "intercept",
        "changed_tow_target": (
            draft.tow_target_ship_id is not None
            and draft.tow_target_ship_id != upstream_tow_target_ship_id
        ),
        "changed_friendly_code": (
            draft.friendly_code is not None
            and draft.friendly_code != upstream_friendly_code
        ),
        "changed_mission": (
            draft.mission is not None and draft.mission != upstream_mission
        ),
        "changed_primary_enemy": (
            draft.primary_enemy_id is not None
            and draft.primary_enemy_id != (upstream_primary_enemy_id or 0)
        ),
        "source": "local_order_draft",
    }


def get_ship_order_draft(
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
    ship_id: int,
) -> dict[str, Any] | None:
    with SessionLocal() as session:
        batch, ship = _factual_ship_context(
            session,
            user_id=user_id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            ship_id=ship_id,
        )
        draft = session.execute(
            select(ShipOrderDraft).where(
                ShipOrderDraft.user_id == user_id,
                ShipOrderDraft.linked_account_id == linked_account_id,
                ShipOrderDraft.game_id == game_id,
                ShipOrderDraft.turn == turn,
                ShipOrderDraft.ship_id == ship_id,
            )
        ).scalar_one_or_none()
        if draft is None:
            return None
        return _serialize(draft, batch=batch, ship=ship)


def upsert_ship_order_draft(
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
    ship_id: int,
    warp: int | None,
    waypoint_x: int | None,
    waypoint_y: int | None,
    movement_mode: str | None,
    intercept_target_ship_id: int | None,
    tow_target_ship_id: int | None = None,
    friendly_code: str | None = None,
    mission: str | None = None,
    primary_enemy_id: int | None = None,
) -> dict[str, Any]:
    with SessionLocal() as session:
        batch, ship = _factual_ship_context(
            session,
            user_id=user_id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
            ship_id=ship_id,
        )

        draft = session.execute(
            select(ShipOrderDraft).where(
                ShipOrderDraft.user_id == user_id,
                ShipOrderDraft.linked_account_id == linked_account_id,
                ShipOrderDraft.game_id == game_id,
                ShipOrderDraft.turn == turn,
                ShipOrderDraft.ship_id == ship_id,
            )
        ).scalar_one_or_none()

        next_movement_mode = (
            movement_mode
            if movement_mode is not None
            else (draft.movement_mode if draft is not None else "waypoint")
        )
        next_mission = (
            mission.strip()
            if mission is not None
            else (
                draft.mission
                if draft is not None and draft.mission is not None
                else _upstream_mission(ship)
            )
        )

        effective_intercept_target = (
            intercept_target_ship_id
            if intercept_target_ship_id is not None
            else (
                draft.intercept_target_ship_id
                if draft is not None
                else None
            )
        )
        if next_movement_mode == "intercept":
            if effective_intercept_target is None:
                raise OrderDraftAccessError(
                    "Intercept movement requires a target ship"
                )
            _validate_intercept_target(
                session,
                batch_id=batch.id,
                ship_id=ship_id,
                target_ship_id=effective_intercept_target,
            )

        stored_tow_target = (
            draft.tow_target_ship_id if draft is not None else None
        )
        upstream_tow_target = _upstream_tow_target(ship)
        effective_tow_target = (
            tow_target_ship_id
            if tow_target_ship_id is not None
            else (
                stored_tow_target
                if stored_tow_target is not None
                else upstream_tow_target
            )
        )

        if _is_tow_mission_name(next_mission):
            if next_movement_mode == "intercept":
                raise OrderDraftAccessError(
                    "Tow mission cannot be combined with Intercept movement"
                )
            if effective_tow_target is None:
                raise OrderDraftAccessError(
                    "Tow mission requires an explicit tow_target_ship_id"
                )
            _validate_tow_target(
                session,
                batch_id=batch.id,
                ship=ship,
                target_ship_id=effective_tow_target,
            )
        elif tow_target_ship_id is not None:
            raise OrderDraftAccessError(
                "tow_target_ship_id requires the Tow mission"
            )

        if draft is None:
            draft = ShipOrderDraft(
                user_id=user_id,
                linked_account_id=linked_account_id,
                game_id=game_id,
                turn=turn,
                ship_id=ship_id,
                base_batch_id=batch.id,
                base_snapshot_hash=batch.snapshot_hash,
                warp=warp,
                waypoint_x=waypoint_x,
                waypoint_y=waypoint_y,
                movement_mode=next_movement_mode,
                intercept_target_ship_id=(
                    effective_intercept_target
                    if next_movement_mode == "intercept"
                    else None
                ),
                tow_target_ship_id=(
                    effective_tow_target
                    if _is_tow_mission_name(next_mission)
                    else None
                ),
                friendly_code=friendly_code,
                mission=mission.strip() if mission is not None else None,
                primary_enemy_id=primary_enemy_id,
            )
            session.add(draft)
        else:
            if warp is not None:
                draft.warp = warp
            if waypoint_x is not None and waypoint_y is not None:
                draft.waypoint_x = waypoint_x
                draft.waypoint_y = waypoint_y
            if movement_mode is not None:
                draft.movement_mode = movement_mode
                if movement_mode == "waypoint":
                    draft.intercept_target_ship_id = None
                else:
                    draft.intercept_target_ship_id = effective_intercept_target
            if friendly_code is not None:
                draft.friendly_code = friendly_code
            if mission is not None:
                draft.mission = mission.strip()
            if _is_tow_mission_name(next_mission):
                draft.tow_target_ship_id = effective_tow_target
            else:
                draft.tow_target_ship_id = None
            if primary_enemy_id is not None:
                draft.primary_enemy_id = primary_enemy_id
            draft.base_batch_id = batch.id
            draft.base_snapshot_hash = batch.snapshot_hash

        session.commit()
        session.refresh(draft)
        return _serialize(draft, batch=batch, ship=ship)


def discard_ship_order_draft(
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
    ship_id: int,
) -> bool:
    with SessionLocal() as session:
        _account(
            session,
            user_id=user_id,
            linked_account_id=linked_account_id,
        )
        result = session.execute(
            delete(ShipOrderDraft).where(
                ShipOrderDraft.user_id == user_id,
                ShipOrderDraft.linked_account_id == linked_account_id,
                ShipOrderDraft.game_id == game_id,
                ShipOrderDraft.turn == turn,
                ShipOrderDraft.ship_id == ship_id,
            )
        )
        session.commit()
        return bool(result.rowcount)
