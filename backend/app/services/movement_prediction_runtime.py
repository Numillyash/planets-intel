from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.ship_observation import ShipObservation
from app.services import movement_prediction as _implementation
from app.services.movement_fuel_policy import (
    WaypointFuelResolution,
    WaypointFuelStatus,
    resolve_waypoint_fuel,
)
from app.services.movement_intercept import Point
from app.services.movement_move_most import MoveMostOrder, MoveMostResult, MoveMostStatus


@dataclass(slots=True)
class _FuelContext:
    owner_slot_id: int
    unlimited_fuel: bool
    ships: dict[int, ShipObservation]
    hulls: list[dict[str, Any]]
    beams: list[dict[str, Any]]
    torpedoes: list[dict[str, Any]]
    engines: list[dict[str, Any]]
    resolutions: dict[int, WaypointFuelResolution] = field(default_factory=dict)


_CONTEXT: ContextVar[_FuelContext | None] = ContextVar(
    "movement_prediction_fuel_context",
    default=None,
)

_ORIGINAL_RESOLVE_MOVE_MOST_ORDER = _implementation.resolve_move_most_order
_ORIGINAL_SERIALIZE_MOVE_MOST = _implementation._serialize_move_most
_ORIGINAL_SERIALIZE_INTERCEPT = _implementation._serialize_intercept
_ORIGINAL_COMMON_WARNINGS = _implementation._common_warnings


def _common_warnings(*, unlimited_fuel: bool) -> list[str]:
    return [
        warning
        for warning in _ORIGINAL_COMMON_WARNINGS(unlimited_fuel=unlimited_fuel)
        if "Fuel-limited distance is not yet applied" not in warning
    ]


def _integer_point(point: Point | None) -> tuple[int | None, int | None]:
    if point is None:
        return None, None
    if not float(point.x).is_integer() or not float(point.y).is_integer():
        return None, None
    return int(point.x), int(point.y)


def _fuel_adjusted_move(order: MoveMostOrder, result: MoveMostResult) -> MoveMostResult:
    context = _CONTEXT.get()
    if context is None:
        return result
    ship = context.ships.get(order.ship_id)
    if ship is None or ship.x is None or ship.y is None:
        return result

    target_x, target_y = _integer_point(order.waypoint)
    fuel = resolve_waypoint_fuel(
        unlimited_fuel=context.unlimited_fuel,
        payload=dict(ship.payload) if isinstance(ship.payload, dict) else {},
        hull_id=ship.hull_id,
        owner_observed=ship.owner_id == context.owner_slot_id,
        hulls=context.hulls,
        beams=context.beams,
        torpedoes=context.torpedoes,
        engines=context.engines,
        warp=order.warp,
        speed_multiplier=order.speed_multiplier,
        origin_x=int(ship.x),
        origin_y=int(ship.y),
        target_x=target_x,
        target_y=target_y,
        requested_distance=result.requested_distance,
        geometric_moved_distance=result.moved_distance,
        geometric_max_distance=result.max_distance,
    )
    context.resolutions[order.ship_id] = fuel

    if fuel.has_position_override:
        assert fuel.override_x is not None
        assert fuel.override_y is not None
        return replace(
            result,
            status=MoveMostStatus.MOVED,
            position=Point(float(fuel.override_x), float(fuel.override_y)),
            moved_distance=fuel.override_moved_distance,
            reached_waypoint=False,
            certain=result.certain and fuel.certain,
            reason=f"{result.reason} {fuel.reason}",
        )

    if fuel.certain:
        return result

    # A known finite-fuel uncertainty can materially change the endpoint. Do
    # not allow the geometric position to flow into warp-well or Intercept as a
    # factual-looking prediction.
    return replace(
        result,
        position=None,
        moved_distance=None,
        reached_waypoint=None,
        certain=False,
        reason=f"{result.reason} Fuel endpoint unresolved: {fuel.reason}",
    )


def _resolve_move_most_order(order: MoveMostOrder) -> MoveMostResult:
    return _fuel_adjusted_move(order, _ORIGINAL_RESOLVE_MOVE_MOST_ORDER(order))


def _fuel_metadata(fuel: WaypointFuelResolution | None) -> dict[str, Any]:
    if fuel is None:
        return {
            "fuel_status": "not_evaluated",
            "movement_mass": None,
            "fuel_available": None,
            "fuel_factor": None,
            "fuel_required": None,
            "fuel_used": None,
            "fuel_limited": None,
            "fuel_basis": "not_evaluated",
            "fuel_reason": "Fuel evaluation was not available for this movement item.",
        }

    if fuel.status == WaypointFuelStatus.UNLIMITED:
        basis = "game_rule_unlimitedfuel"
    elif fuel.status == WaypointFuelStatus.NOT_REQUIRED:
        basis = "no_positive_movement"
    else:
        basis = "factual_private_snapshot+persisted_rule_catalog"

    return {
        "fuel_status": fuel.status.value,
        "movement_mass": fuel.movement_mass,
        "fuel_available": fuel.fuel_available,
        "fuel_factor": fuel.fuel_factor,
        "fuel_required": fuel.fuel_required,
        "fuel_used": fuel.fuel_used,
        "fuel_limited": fuel.fuel_limited,
        "fuel_basis": basis,
        "fuel_reason": fuel.reason,
    }


def _serialize_move_most(*args: Any, **kwargs: Any) -> dict[str, Any]:
    warnings = list(kwargs.get("warnings") or [])
    draft = kwargs.get("draft")
    context = _CONTEXT.get()
    fuel = (
        context.resolutions.get(int(draft.ship_id))
        if context is not None and draft is not None
        else None
    )
    if fuel is not None and fuel.status not in {
        WaypointFuelStatus.UNLIMITED,
        WaypointFuelStatus.NOT_REQUIRED,
    }:
        warnings.append(
            "Fuel uses the current factual private load; pre-movement transfers, "
            "Crystal web drain, Tow mass and other fuel-state changes are not yet applied."
        )
        if not fuel.certain:
            warnings.append(f"Fuel endpoint unresolved: {fuel.reason}")
    kwargs["warnings"] = warnings
    result = _ORIGINAL_SERIALIZE_MOVE_MOST(*args, **kwargs)
    result.update(_fuel_metadata(fuel))
    return result


def _serialize_intercept(*args: Any, **kwargs: Any) -> dict[str, Any]:
    context = _CONTEXT.get()
    warnings = list(kwargs.get("warnings") or [])
    result = _ORIGINAL_SERIALIZE_INTERCEPT(*args, **kwargs)
    if context is not None and context.unlimited_fuel:
        result.update(
            {
                "fuel_status": "unlimited",
                "movement_mass": None,
                "fuel_available": None,
                "fuel_factor": None,
                "fuel_required": None,
                "fuel_used": None,
                "fuel_limited": False,
                "fuel_basis": "game_rule_unlimitedfuel",
                "fuel_reason": "Game rules provide unlimited movement fuel.",
            }
        )
        return result

    warnings.append(
        "Finite-fuel Intercept remains a geometry preview until Tow and Intercept "
        "fuel ordering are integrated."
    )
    result["certain"] = False
    result["warnings"] = warnings
    result.update(
        {
            "fuel_status": "unresolved_intercept",
            "movement_mass": None,
            "fuel_available": None,
            "fuel_factor": None,
            "fuel_required": None,
            "fuel_used": None,
            "fuel_limited": None,
            "fuel_basis": "deferred_until_tow_and_intercept_fuel",
            "fuel_reason": (
                "Fuel-limited Intercept is not yet applied; Tow must be resolved "
                "ahead of Move Most/Intercept first."
            ),
        }
    )
    return result


# The implementation resolves these helpers from module globals at call time,
# exactly like the battle simulator runtime facade. ContextVar keeps per-request
# factual fuel inputs isolated between concurrent requests.
_implementation.resolve_move_most_order = _resolve_move_most_order
_implementation._serialize_move_most = _serialize_move_most
_implementation._serialize_intercept = _serialize_intercept
_implementation._common_warnings = _common_warnings


def get_draft_movement_prediction(
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
) -> dict[str, Any]:
    with SessionLocal() as session:
        batch = _implementation._latest_batch(
            session,
            user_id=user_id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
        )
        ships = list(
            session.execute(
                select(ShipObservation).where(ShipObservation.batch_id == batch.id)
            ).scalars().all()
        )
        catalog = session.execute(
            select(GameRuleCatalog).where(GameRuleCatalog.game_id == game_id)
        ).scalar_one_or_none()

    settings = dict(catalog.settings) if catalog is not None else {}
    context = _FuelContext(
        owner_slot_id=int(batch.source_player_slot_id),
        unlimited_fuel=bool(settings.get("unlimitedfuel", False)),
        ships={int(ship.ship_id): ship for ship in ships},
        hulls=list(catalog.hulls) if catalog is not None else [],
        beams=list(catalog.beams) if catalog is not None else [],
        torpedoes=list(catalog.torpedos) if catalog is not None else [],
        engines=list(catalog.engines) if catalog is not None else [],
    )
    token = _CONTEXT.set(context)
    try:
        return _implementation.get_draft_movement_prediction(
            user_id=user_id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
        )
    finally:
        _CONTEXT.reset(token)


MovementPredictionAccessError = _implementation.MovementPredictionAccessError
MovementPredictionNotFound = _implementation.MovementPredictionNotFound

__all__ = [
    "MovementPredictionAccessError",
    "MovementPredictionNotFound",
    "get_draft_movement_prediction",
]
