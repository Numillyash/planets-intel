from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Any, Mapping

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.planet_observation import PlanetObservation
from app.models.ship_observation import ShipObservation
from app.models.ship_order_draft import ShipOrderDraft
from app.services import movement_prediction as _implementation
from app.services.movement_fuel_policy import (
    WaypointFuelResolution,
    WaypointFuelStatus,
    resolve_waypoint_fuel,
)
from app.services.movement_intercept import (
    InterceptMode,
    InterceptOrder,
    InterceptResult,
    InterceptStatus,
    Point,
)
from app.services.movement_move_most import (
    MoveMostOrder,
    MoveMostResult,
    MoveMostStatus,
)
from app.services.movement_tow import (
    TowAttempt,
    TowLockStatus,
    TowShipState,
    hull_engine_count,
    payload_is_tow_mission,
    payload_tow_target_id,
    resolve_strict_tow_locks,
)
from app.services.movement_warp_well import (
    PlanetWarpWell,
    WarpWellResult,
    resolve_warp_well,
)


TOW_MISSION_NAMES = frozenset({"tow", "try to tow", "mission #6"})

@dataclass(frozen=True, slots=True)
class _TowRuntimeOutcome:
    role: str
    tower_ship_id: int | None
    target_ship_id: int | None
    lock_status: str
    status: str
    certain: bool
    position: Point | None
    pre_well_position: Point | None
    waypoint: Point | None
    requested_distance: float | None
    max_distance: float | None
    moved_distance: float | None
    reached_waypoint: bool | None
    move_status: MoveMostStatus | None
    route_warp: int | None
    route_speed_multiplier: float | None
    reason: str
    warp_well: WarpWellResult | None = None


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
    tow_outcomes: dict[int, _TowRuntimeOutcome] = field(default_factory=dict)
    tow_known_positions: dict[int, Point] = field(default_factory=dict)


_CONTEXT: ContextVar[_FuelContext | None] = ContextVar(
    "movement_prediction_fuel_context",
    default=None,
)

_ORIGINAL_RESOLVE_MOVE_MOST_ORDER = _implementation.resolve_move_most_order
_ORIGINAL_RESOLVE_INTERCEPTS = _implementation.resolve_intercepts
_ORIGINAL_SERIALIZE_MOVE_MOST = _implementation._serialize_move_most
_ORIGINAL_SERIALIZE_INTERCEPT = _implementation._serialize_intercept
_ORIGINAL_COMMON_WARNINGS = _implementation._common_warnings


def _payload(ship: ShipObservation) -> dict[str, Any]:
    return dict(ship.payload) if isinstance(ship.payload, dict) else {}


def _effective_warp(
    ship: ShipObservation,
    draft: ShipOrderDraft | None,
) -> int | None:
    if draft is not None and draft.warp is not None:
        return int(draft.warp)
    if ship.warp is not None:
        return int(ship.warp)
    value = _implementation._payload_int(_payload(ship), "warp")
    return int(value) if value is not None else None


def _effective_waypoint(
    ship: ShipObservation,
    draft: ShipOrderDraft | None,
) -> Point | None:
    if (
        draft is not None
        and draft.waypoint_x is not None
        and draft.waypoint_y is not None
    ):
        return Point(float(draft.waypoint_x), float(draft.waypoint_y))

    payload = _payload(ship)
    x = _implementation._payload_int(
        payload,
        "waypointx",
        "targetx",
        "waypoint_x",
    )
    y = _implementation._payload_int(
        payload,
        "waypointy",
        "targety",
        "waypoint_y",
    )
    if x is None or y is None:
        return None
    return Point(float(x), float(y))


def _draft_mission_is_tow(draft: ShipOrderDraft | None) -> bool:
    return (
        draft is not None
        and draft.mission is not None
        and draft.mission.strip().casefold() in TOW_MISSION_NAMES
    )


def _effective_is_tow(
    ship: ShipObservation,
    draft: ShipOrderDraft | None,
) -> bool:
    if draft is not None and draft.mission is not None:
        return _draft_mission_is_tow(draft)
    return payload_is_tow_mission(_payload(ship))


def _effective_tow_target_id(
    ship: ShipObservation,
    draft: ShipOrderDraft | None,
) -> int | None:
    draft_target = (
        getattr(draft, "tow_target_ship_id", None)
        if draft is not None
        else None
    )
    if draft_target is not None:
        return int(draft_target)

    # A local draft that newly selects Tow must never inherit a stale
    # mission1target from a factual non-Tow order. Existing factual Tow may
    # still use its observed target when the draft only changes another field.
    if _draft_mission_is_tow(draft) and not payload_is_tow_mission(_payload(ship)):
        return None
    return payload_tow_target_id(_payload(ship))


def _strict_tow_speed_multiplier(
    ship: ShipObservation,
    *,
    hull_names: Mapping[int, str],
) -> float | None:
    if ship.hull_id is None:
        return None
    hull_name = hull_names.get(int(ship.hull_id))
    if hull_name is None:
        return None
    return (
        2.0
        if hull_name.casefold() in _implementation.GRAVITONIC_HULL_NAMES
        else 1.0
    )


def _tow_state(
    ship: ShipObservation,
    *,
    draft: ShipOrderDraft | None,
    hulls: list[dict[str, Any]],
    hull_names: Mapping[int, str],
) -> TowShipState:
    payload = _payload(ship)
    waypoint = _effective_waypoint(ship, draft)
    return TowShipState(
        ship_id=int(ship.ship_id),
        x=int(ship.x) if ship.x is not None else None,
        y=int(ship.y) if ship.y is not None else None,
        warp=_effective_warp(ship, draft),
        waypoint_x=(
            int(waypoint.x)
            if waypoint is not None and float(waypoint.x).is_integer()
            else None
        ),
        waypoint_y=(
            int(waypoint.y)
            if waypoint is not None and float(waypoint.y).is_integer()
            else None
        ),
        fuel=_implementation._payload_int(payload, "neutronium", "fuel"),
        engine_count=hull_engine_count(
            hull_id=ship.hull_id,
            hulls=hulls,
        ),
        speed_multiplier=_strict_tow_speed_multiplier(
            ship,
            hull_names=hull_names,
        ),
    )


def _unresolved_tow_outcome(
    *,
    role: str,
    tower_ship_id: int | None,
    target_ship_id: int | None,
    lock_status: str,
    status: str,
    route_warp: int | None,
    route_speed_multiplier: float | None,
    waypoint: Point | None,
    reason: str,
    pre_well_position: Point | None = None,
    requested_distance: float | None = None,
    max_distance: float | None = None,
    moved_distance: float | None = None,
    reached_waypoint: bool | None = None,
    move_status: MoveMostStatus | None = None,
    warp_well: WarpWellResult | None = None,
) -> _TowRuntimeOutcome:
    return _TowRuntimeOutcome(
        role=role,
        tower_ship_id=tower_ship_id,
        target_ship_id=target_ship_id,
        lock_status=lock_status,
        status=status,
        certain=False,
        position=None,
        pre_well_position=pre_well_position,
        waypoint=waypoint,
        requested_distance=requested_distance,
        max_distance=max_distance,
        moved_distance=moved_distance,
        reached_waypoint=reached_waypoint,
        move_status=move_status,
        route_warp=route_warp,
        route_speed_multiplier=route_speed_multiplier,
        reason=reason,
        warp_well=warp_well,
    )


def _known_tow_outcome(
    *,
    role: str,
    tower_ship_id: int,
    target_ship_id: int,
    route: MoveMostResult,
    route_warp: int,
    route_speed_multiplier: float,
    reason: str,
    warp_well: WarpWellResult | None,
) -> _TowRuntimeOutcome:
    assert route.position is not None
    final_position = (
        warp_well.position
        if (
            warp_well is not None
            and warp_well.certain
            and warp_well.position is not None
        )
        else route.position
    )
    return _TowRuntimeOutcome(
        role=role,
        tower_ship_id=tower_ship_id,
        target_ship_id=target_ship_id,
        lock_status=TowLockStatus.LOCKED.value,
        status=("locked" if role == "tower" else "towed"),
        certain=True,
        position=final_position,
        pre_well_position=route.position,
        waypoint=route.waypoint,
        requested_distance=route.requested_distance,
        max_distance=route.max_distance,
        moved_distance=route.moved_distance,
        reached_waypoint=route.reached_waypoint,
        move_status=route.status,
        route_warp=route_warp,
        route_speed_multiplier=route_speed_multiplier,
        reason=reason,
        warp_well=warp_well,
    )


def _build_tow_outcomes(
    *,
    ships: list[ShipObservation],
    drafts: list[ShipOrderDraft],
    owner_slot_id: int,
    hulls: list[dict[str, Any]],
    hull_names: Mapping[int, str],
    unlimited_fuel: bool,
    gravity_wells_enabled: bool,
    planet_wells: list[PlanetWarpWell],
) -> tuple[dict[int, _TowRuntimeOutcome], dict[int, Point]]:
    ships_by_id = {int(ship.ship_id): ship for ship in ships}
    draft_by_ship_id = {int(draft.ship_id): draft for draft in drafts}

    states = {
        ship_id: _tow_state(
            ship,
            draft=draft_by_ship_id.get(ship_id),
            hulls=hulls,
            hull_names=hull_names,
        )
        for ship_id, ship in ships_by_id.items()
    }

    attempts: list[TowAttempt] = []
    tower_outcomes: dict[int, _TowRuntimeOutcome] = {}
    target_outcomes: dict[int, _TowRuntimeOutcome] = {}

    for ship_id, ship in ships_by_id.items():
        if ship.owner_id != owner_slot_id:
            continue
        draft = draft_by_ship_id.get(ship_id)
        if not _effective_is_tow(ship, draft):
            continue

        state = states[ship_id]
        waypoint = (
            Point(float(state.waypoint_x), float(state.waypoint_y))
            if state.waypoint_x is not None and state.waypoint_y is not None
            else None
        )
        target_id = _effective_tow_target_id(ship, draft)
        if target_id is None:
            tower_outcomes[ship_id] = _unresolved_tow_outcome(
                role="tower",
                tower_ship_id=ship_id,
                target_ship_id=None,
                lock_status=TowLockStatus.UNKNOWN.value,
                status="draft_tow_target_unresolved",
                route_warp=state.warp,
                route_speed_multiplier=state.speed_multiplier,
                waypoint=waypoint,
                reason=(
                    "Tow mission is selected, but no explicit local Tow target or "
                    "eligible factual Tow target is available. Ordinary movement is "
                    "withheld rather than reusing stale mission1target state."
                ),
            )
            continue

        attempts.append(
            TowAttempt(
                tower_ship_id=ship_id,
                target_ship_id=target_id,
            )
        )

    if attempts:
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=attempts,
            unlimited_fuel=unlimited_fuel,
        )
    else:
        resolution = None

    for result in resolution.attempts if resolution is not None else ():
        tower_id = int(result.tower_ship_id)
        target_id = (
            int(result.target_ship_id)
            if result.target_ship_id is not None
            else None
        )

        # Certain non-locks continue through normal Move Most/Intercept.
        if result.certain and not result.locked:
            continue

        tower_state = states.get(tower_id)
        tower_ship = ships_by_id.get(tower_id)
        target_ship = ships_by_id.get(target_id) if target_id is not None else None
        tower_waypoint = (
            Point(float(tower_state.waypoint_x), float(tower_state.waypoint_y))
            if (
                tower_state is not None
                and tower_state.waypoint_x is not None
                and tower_state.waypoint_y is not None
            )
            else None
        )
        route_warp = tower_state.warp if tower_state is not None else None
        route_speed = (
            tower_state.speed_multiplier if tower_state is not None else None
        )

        if not result.locked:
            reason = (
                f"{result.reason} Tow outcome can change this ship before "
                "Move Most/Intercept, so later movement is withheld."
            )
            tower_outcomes[tower_id] = _unresolved_tow_outcome(
                role="tower",
                tower_ship_id=tower_id,
                target_ship_id=target_id,
                lock_status=result.status.value,
                status=result.status.value,
                route_warp=route_warp,
                route_speed_multiplier=route_speed,
                waypoint=tower_waypoint,
                reason=reason,
            )
            if target_id is not None and target_ship is not None:
                ambiguous_tower_id = (
                    None
                    if result.status
                    in {
                        TowLockStatus.AMBIGUOUS_CONTEST,
                        TowLockStatus.UNSUPPORTED_CHAIN,
                    }
                    else tower_id
                )
                target_outcomes.setdefault(
                    target_id,
                    _unresolved_tow_outcome(
                        role="target",
                        tower_ship_id=ambiguous_tower_id,
                        target_ship_id=target_id,
                        lock_status=result.status.value,
                        status="tow_target_unresolved",
                        route_warp=route_warp,
                        route_speed_multiplier=route_speed,
                        waypoint=tower_waypoint,
                        reason=reason,
                    ),
                )
            continue

        if (
            tower_state is None
            or tower_ship is None
            or target_id is None
            or target_ship is None
            or tower_ship.x is None
            or tower_ship.y is None
            or route_warp is None
            or route_speed is None
        ):
            reason = (
                "Tow lock is known, but the towing route cannot be reconstructed "
                "from factual position/warp/hull data."
            )
            tower_outcomes[tower_id] = _unresolved_tow_outcome(
                role="tower",
                tower_ship_id=tower_id,
                target_ship_id=target_id,
                lock_status=TowLockStatus.LOCKED.value,
                status="locked_route_unresolved",
                route_warp=route_warp,
                route_speed_multiplier=route_speed,
                waypoint=tower_waypoint,
                reason=reason,
            )
            if target_id is not None and target_ship is not None:
                target_outcomes[target_id] = _unresolved_tow_outcome(
                    role="target",
                    tower_ship_id=tower_id,
                    target_ship_id=target_id,
                    lock_status=TowLockStatus.LOCKED.value,
                    status="locked_route_unresolved",
                    route_warp=route_warp,
                    route_speed_multiplier=route_speed,
                    waypoint=tower_waypoint,
                    reason=reason,
                )
            continue

        route = _ORIGINAL_RESOLVE_MOVE_MOST_ORDER(
            MoveMostOrder(
                ship_id=tower_id,
                origin=Point(float(tower_ship.x), float(tower_ship.y)),
                waypoint=tower_waypoint,
                warp=route_warp,
                speed_multiplier=route_speed,
            )
        )

        if not route.certain or route.position is None:
            reason = (
                "Tow lock is known, but the towing ship endpoint is unresolved. "
                f"{route.reason}"
            )
            tower_outcomes[tower_id] = _unresolved_tow_outcome(
                role="tower",
                tower_ship_id=tower_id,
                target_ship_id=target_id,
                lock_status=TowLockStatus.LOCKED.value,
                status="locked_route_unresolved",
                route_warp=route_warp,
                route_speed_multiplier=route_speed,
                waypoint=tower_waypoint,
                reason=reason,
                requested_distance=route.requested_distance,
                max_distance=route.max_distance,
                moved_distance=route.moved_distance,
                reached_waypoint=route.reached_waypoint,
                move_status=route.status,
            )
            target_outcomes[target_id] = _unresolved_tow_outcome(
                role="target",
                tower_ship_id=tower_id,
                target_ship_id=target_id,
                lock_status=TowLockStatus.LOCKED.value,
                status="locked_route_unresolved",
                route_warp=route_warp,
                route_speed_multiplier=route_speed,
                waypoint=tower_waypoint,
                reason=reason,
                requested_distance=route.requested_distance,
                max_distance=route.max_distance,
                moved_distance=route.moved_distance,
                reached_waypoint=route.reached_waypoint,
                move_status=route.status,
            )
            continue

        well: WarpWellResult | None = None
        if gravity_wells_enabled:
            well = resolve_warp_well(
                ship_id=tower_id,
                pre_well_position=route.position,
                warp=route_warp,
                moved_distance=float(route.moved_distance or 0.0),
                planets=planet_wells,
            )
            if not well.certain or well.position is None:
                reason = (
                    "Tow lock and pre-well endpoint are known, but the endpoint "
                    "lies in multiple planetary warp wells and the authoritative "
                    "tie-break is not modelled. The whole Tow pair remains withheld."
                )
                tower_outcomes[tower_id] = _unresolved_tow_outcome(
                    role="tower",
                    tower_ship_id=tower_id,
                    target_ship_id=target_id,
                    lock_status=TowLockStatus.LOCKED.value,
                    status="locked_route_unresolved",
                    route_warp=route_warp,
                    route_speed_multiplier=route_speed,
                    waypoint=tower_waypoint,
                    reason=reason,
                    pre_well_position=route.position,
                    requested_distance=route.requested_distance,
                    max_distance=route.max_distance,
                    moved_distance=route.moved_distance,
                    reached_waypoint=route.reached_waypoint,
                    move_status=route.status,
                    warp_well=well,
                )
                target_outcomes[target_id] = _unresolved_tow_outcome(
                    role="target",
                    tower_ship_id=tower_id,
                    target_ship_id=target_id,
                    lock_status=TowLockStatus.LOCKED.value,
                    status="locked_route_unresolved",
                    route_warp=route_warp,
                    route_speed_multiplier=route_speed,
                    waypoint=tower_waypoint,
                    reason=reason,
                    pre_well_position=route.position,
                    requested_distance=route.requested_distance,
                    max_distance=route.max_distance,
                    moved_distance=route.moved_distance,
                    reached_waypoint=route.reached_waypoint,
                    move_status=route.status,
                    warp_well=well,
                )
                continue

        reason = (
            "Strict owner-visible Tow lock and ordinary planetary warp-well "
            "resolution are deterministic in the verified unlimited-fuel subset; "
            "tower and target share the same post-well endpoint before later "
            "movement phases."
        )
        tower_outcomes[tower_id] = _known_tow_outcome(
            role="tower",
            tower_ship_id=tower_id,
            target_ship_id=target_id,
            route=route,
            route_warp=route_warp,
            route_speed_multiplier=route_speed,
            reason=reason,
            warp_well=well,
        )
        target_outcomes[target_id] = _known_tow_outcome(
            role="target",
            tower_ship_id=tower_id,
            target_ship_id=target_id,
            route=route,
            route_warp=route_warp,
            route_speed_multiplier=route_speed,
            reason=reason,
            warp_well=well,
        )

    outcomes = dict(target_outcomes)
    # A ship that is itself a tower in an unresolved chain is presented as the
    # tower participant rather than being overwritten by its target role.
    outcomes.update(tower_outcomes)
    known_positions = {
        ship_id: outcome.position
        for ship_id, outcome in outcomes.items()
        if outcome.certain and outcome.position is not None
    }
    return outcomes, known_positions


def _common_warnings(*, unlimited_fuel: bool) -> list[str]:
    warnings = []
    for warning in _ORIGINAL_COMMON_WARNINGS(unlimited_fuel=unlimited_fuel):
        lowered = warning.casefold()
        if "tow resolution" in lowered:
            continue
        if "fuel-limited distance is not yet applied" in lowered:
            continue
        warnings.append(warning)

    warnings.insert(
        0,
        (
            "Geometry preview: the verified strict owner-visible Tow subset is "
            "resolved before Move Most/Intercept. Unlimited-fuel ordinary planetary "
            "warp-well capture is included when the well is unambiguous. Finite-fuel "
            "Tow, Tow contests/chains, overlapping-well tie-breaks, mine impacts, "
            "hyperjump/chunnel and other unsupported Host movement substeps remain "
            "fail-closed."
        ),
    )
    return warnings


def _integer_point(point: Point | None) -> tuple[int | None, int | None]:
    if point is None:
        return None, None
    if not float(point.x).is_integer() or not float(point.y).is_integer():
        return None, None
    return int(point.x), int(point.y)


def _tow_move_result(
    order: MoveMostOrder,
    outcome: _TowRuntimeOutcome,
) -> MoveMostResult:
    status = outcome.move_status
    if status is None:
        status = (
            MoveMostStatus.MOVED
            if outcome.certain and (outcome.moved_distance or 0.0) > 0.0
            else MoveMostStatus.UNRESOLVED_INELIGIBLE
        )
    return MoveMostResult(
        ship_id=order.ship_id,
        status=status,
        position=outcome.position,
        waypoint=outcome.waypoint,
        requested_distance=outcome.requested_distance,
        max_distance=float(outcome.max_distance or 0.0),
        moved_distance=outcome.moved_distance,
        reached_waypoint=outcome.reached_waypoint,
        certain=outcome.certain,
        reason=outcome.reason,
    )


def _fuel_adjusted_move(order: MoveMostOrder, result: MoveMostResult) -> MoveMostResult:
    context = _CONTEXT.get()
    if context is None:
        return result

    tow = context.tow_outcomes.get(order.ship_id)
    if tow is not None:
        return _tow_move_result(order, tow)

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


def _tow_intercept_result(
    order: InterceptOrder,
    outcome: _TowRuntimeOutcome,
) -> InterceptResult:
    if outcome.certain:
        status = (
            InterceptStatus.MOVED
            if (outcome.moved_distance or 0.0) > 0.0
            else InterceptStatus.STAYED_NO_SPEED
        )
    else:
        status = InterceptStatus.UNRESOLVED_POST_MOVE
    return InterceptResult(
        ship_id=order.ship_id,
        status=status,
        position=outcome.position,
        target_ship_id=order.target_ship_id,
        target_position=None,
        requested_distance=outcome.requested_distance,
        moved_distance=outcome.moved_distance,
        certain=outcome.certain,
        reason=outcome.reason,
        pre_final_position=(
            outcome.pre_well_position if outcome.certain else None
        ),
    )


def _resolve_intercepts(
    orders: list[InterceptOrder],
    *,
    prior_final_positions: Mapping[int, Point],
    mode: InterceptMode,
) -> dict[int, InterceptResult]:
    context = _CONTEXT.get()
    if context is None or not context.tow_outcomes:
        return _ORIGINAL_RESOLVE_INTERCEPTS(
            orders,
            prior_final_positions=prior_final_positions,
            mode=mode,
        )

    augmented_positions = dict(prior_final_positions)
    augmented_positions.update(context.tow_known_positions)

    active_orders = [
        order for order in orders if order.ship_id not in context.tow_outcomes
    ]
    results = _ORIGINAL_RESOLVE_INTERCEPTS(
        active_orders,
        prior_final_positions=augmented_positions,
        mode=mode,
    )

    for order in orders:
        outcome = context.tow_outcomes.get(order.ship_id)
        if outcome is not None:
            results[order.ship_id] = _tow_intercept_result(order, outcome)
    return results


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


def _tow_fuel_metadata(
    *,
    unlimited_fuel: bool,
) -> dict[str, Any]:
    if unlimited_fuel:
        return {
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
    return {
        "fuel_status": "unresolved_tow",
        "movement_mass": None,
        "fuel_available": None,
        "fuel_factor": None,
        "fuel_required": None,
        "fuel_used": None,
        "fuel_limited": None,
        "fuel_basis": "deferred_until_tow_phase_fuel_and_mass",
        "fuel_reason": (
            "Finite-fuel Tow requires Tow-phase neutronium state and combined "
            "tower+target physical mass."
        ),
    }


def _apply_tow_metadata(
    result: dict[str, Any],
    *,
    outcome: _TowRuntimeOutcome,
    context: _FuelContext,
) -> dict[str, Any]:
    counterpart_id = (
        outcome.target_ship_id
        if outcome.role == "tower"
        else outcome.tower_ship_id
    )
    counterpart = (
        context.ships.get(counterpart_id)
        if counterpart_id is not None
        else None
    )
    warnings = list(result.get("warnings") or [])
    warnings.append(
        (
            "Tow resolves before Move Most/Intercept; ordinary movement for this "
            "ship is suppressed by the Tow-phase prediction."
            if outcome.certain
            else
            "Tow outcome is unresolved; this ship is withheld from later movement "
            "phases instead of falling back to a false Move Most/Intercept endpoint."
        )
    )

    well = outcome.warp_well
    result.update(
        {
            "movement_mode": "tow",
            "phase": "tow",
            "status": outcome.status,
            "certain": outcome.certain,
            "waypoint_x": (
                outcome.waypoint.x if outcome.waypoint is not None else None
            ),
            "waypoint_y": (
                outcome.waypoint.y if outcome.waypoint is not None else None
            ),
            "target_ship_id": counterpart_id,
            "target_x": (
                float(counterpart.x)
                if counterpart is not None and counterpart.x is not None
                else None
            ),
            "target_y": (
                float(counterpart.y)
                if counterpart is not None and counterpart.y is not None
                else None
            ),
            "target_warp": (
                int(counterpart.warp)
                if counterpart is not None and counterpart.warp is not None
                else None
            ),
            "target_speed_multiplier": None,
            "target_standard_max_distance": None,
            "pre_well_x": (
                outcome.pre_well_position.x
                if outcome.pre_well_position is not None
                else None
            ),
            "pre_well_y": (
                outcome.pre_well_position.y
                if outcome.pre_well_position is not None
                else None
            ),
            "warp_well_status": well.status.value if well is not None else None,
            "warp_well_planet_id": well.planet_id if well is not None else None,
            "warp_well_planet_name": (
                well.planet_name if well is not None else None
            ),
            "warp_well_pull_distance": (
                well.distance_to_planet if well is not None else None
            ),
            "predicted_x": (
                outcome.position.x if outcome.position is not None else None
            ),
            "predicted_y": (
                outcome.position.y if outcome.position is not None else None
            ),
            "requested_distance": outcome.requested_distance,
            "max_distance": outcome.max_distance,
            "moved_distance": outcome.moved_distance,
            "warp": outcome.route_warp,
            "speed_multiplier": (
                outcome.route_speed_multiplier
                if outcome.route_speed_multiplier is not None
                else 1.0
            ),
            "reason": outcome.reason,
            "warnings": warnings,
            "tow_role": outcome.role,
            "tow_tower_ship_id": outcome.tower_ship_id,
            "tow_target_ship_id": outcome.target_ship_id,
            "tow_lock_status": outcome.lock_status,
        }
    )
    result.update(_tow_fuel_metadata(unlimited_fuel=context.unlimited_fuel))
    return result


def _serialize_move_most(*args: Any, **kwargs: Any) -> dict[str, Any]:
    warnings = list(kwargs.get("warnings") or [])
    draft = kwargs.get("draft")
    context = _CONTEXT.get()
    tow = (
        context.tow_outcomes.get(int(draft.ship_id))
        if context is not None and draft is not None
        else None
    )
    if tow is not None and context is not None:
        kwargs["warnings"] = warnings
        result = _ORIGINAL_SERIALIZE_MOVE_MOST(*args, **kwargs)
        return _apply_tow_metadata(result, outcome=tow, context=context)

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
    draft = kwargs.get("draft")
    tow = (
        context.tow_outcomes.get(int(draft.ship_id))
        if context is not None and draft is not None
        else None
    )
    if tow is not None and context is not None:
        kwargs["warnings"] = warnings
        result = _ORIGINAL_SERIALIZE_INTERCEPT(*args, **kwargs)
        return _apply_tow_metadata(result, outcome=tow, context=context)

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
        "Finite-fuel Intercept remains a geometry preview until Intercept fuel "
        "ordering and any unresolved finite-fuel Tow dependency are integrated."
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
            "fuel_basis": "deferred_until_intercept_fuel",
            "fuel_reason": (
                "Fuel-limited Intercept is not yet applied; any finite-fuel Tow "
                "dependency must also be resolved first."
            ),
        }
    )
    return result


# The implementation resolves these helpers from module globals at call time,
# exactly like the battle simulator runtime facade. ContextVar keeps per-request
# factual movement inputs isolated between concurrent requests.
_implementation.resolve_move_most_order = _resolve_move_most_order
_implementation.resolve_intercepts = _resolve_intercepts
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
        drafts = list(
            session.execute(
                select(ShipOrderDraft).where(
                    ShipOrderDraft.user_id == user_id,
                    ShipOrderDraft.linked_account_id == linked_account_id,
                    ShipOrderDraft.game_id == game_id,
                    ShipOrderDraft.turn == turn,
                )
            ).scalars().all()
        )
        planets = list(
            session.execute(
                select(PlanetObservation).where(
                    PlanetObservation.batch_id == batch.id,
                    PlanetObservation.x.is_not(None),
                    PlanetObservation.y.is_not(None),
                )
            ).scalars().all()
        )
        catalog = session.execute(
            select(GameRuleCatalog).where(GameRuleCatalog.game_id == game_id)
        ).scalar_one_or_none()

    settings = dict(catalog.settings) if catalog is not None else {}
    hulls = list(catalog.hulls) if catalog is not None else []
    hull_names = _implementation._hull_name_by_id(catalog)
    unlimited_fuel = bool(settings.get("unlimitedfuel", False))
    gravity_wells_enabled = bool(settings.get("gravitywells", True))
    planet_wells = [
        PlanetWarpWell(
            planet_id=int(planet.planet_id),
            name=planet.name,
            position=Point(float(planet.x), float(planet.y)),
        )
        for planet in planets
        if planet.x is not None and planet.y is not None
    ]

    tow_outcomes, tow_known_positions = _build_tow_outcomes(
        ships=ships,
        drafts=drafts,
        owner_slot_id=int(batch.source_player_slot_id),
        hulls=hulls,
        hull_names=hull_names,
        unlimited_fuel=unlimited_fuel,
        gravity_wells_enabled=gravity_wells_enabled,
        planet_wells=planet_wells,
    )

    context = _FuelContext(
        owner_slot_id=int(batch.source_player_slot_id),
        unlimited_fuel=unlimited_fuel,
        ships={int(ship.ship_id): ship for ship in ships},
        hulls=hulls,
        beams=list(catalog.beams) if catalog is not None else [],
        torpedoes=list(catalog.torpedos) if catalog is not None else [],
        engines=list(catalog.engines) if catalog is not None else [],
        tow_outcomes=tow_outcomes,
        tow_known_positions=tow_known_positions,
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
