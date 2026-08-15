from __future__ import annotations

import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.planet_observation import PlanetObservation
from app.models.planets_account import PlanetsAccount
from app.models.private_observation_batch import PrivateObservationBatch
from app.models.ship_observation import ShipObservation
from app.models.ship_order_draft import ShipOrderDraft
from app.services.movement_intercept import (
    InterceptMode,
    InterceptOrder,
    InterceptResult,
    Point,
    resolve_intercepts,
)
from app.services.movement_move_most import (
    MoveMostOrder,
    MoveMostResult,
    maximum_distance,
    resolve_move_most_order,
)
from app.services.movement_warp_well import (
    PlanetWarpWell,
    WarpWellResult,
    WarpWellStatus,
    resolve_warp_well,
)


class MovementPredictionAccessError(Exception):
    pass


class MovementPredictionNotFound(Exception):
    pass


GRAVITONIC_HULL_NAMES = frozenset(
    {
        "meteor class blockade runner",
        "br4 gun boat",
        "br5 kaye class torpedo boat",
    }
)


def _payload_int(payload: dict[str, Any], *keys: str) -> int | None:
    normalized = {key.casefold() for key in keys}
    for key, value in payload.items():
        if str(key).casefold() not in normalized:
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


def _latest_batch(
    session: Session,
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
) -> PrivateObservationBatch:
    account = session.execute(
        select(PlanetsAccount).where(
            PlanetsAccount.id == linked_account_id,
            PlanetsAccount.user_id == user_id,
            PlanetsAccount.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if account is None:
        raise MovementPredictionAccessError(
            "Linked Planets.nu account is unavailable"
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
        raise MovementPredictionNotFound(
            "No factual snapshot is stored for this observer and game"
        )
    if batch.turn != turn:
        raise MovementPredictionAccessError(
            "Movement prediction is only available for the latest factual turn"
        )
    return batch


def _hull_name_by_id(catalog: GameRuleCatalog | None) -> dict[int, str]:
    if catalog is None:
        return {}
    result: dict[int, str] = {}
    for hull in catalog.hulls:
        hull_id = hull.get("id")
        name = hull.get("name")
        if isinstance(hull_id, int) and isinstance(name, str):
            result[hull_id] = name
    return result


def _speed_multiplier(
    ship: ShipObservation,
    *,
    hull_names: dict[int, str],
) -> float:
    if ship.hull_id is None:
        return 1.0
    hull_name = hull_names.get(ship.hull_id)
    if hull_name is None:
        return 1.0
    return 2.0 if hull_name.casefold() in GRAVITONIC_HULL_NAMES else 1.0


def _common_warnings(
    *,
    unlimited_fuel: bool,
) -> list[str]:
    warnings = [
        (
            "Geometry preview only: tow resolution, mine impacts, "
            "hyperjump/chunnel and other Host movement substeps are not yet applied."
        )
    ]
    if not unlimited_fuel:
        warnings.append(
            "Fuel-limited distance is not yet applied to this prediction."
        )
    return warnings


def _displacement(
    ship: ShipObservation,
    position: Point | None,
) -> float | None:
    if ship.x is None or ship.y is None or position is None:
        return None
    return math.hypot(position.x - float(ship.x), position.y - float(ship.y))


def _warp_well_reason(
    base_reason: str,
    well: WarpWellResult | None,
) -> str:
    if well is None:
        return base_reason
    if well.status == WarpWellStatus.CAPTURED:
        label = well.planet_name or f"planet #{well.planet_id}"
        return f"{base_reason} Planetary warp well pulls the ship into orbit of {label}."
    if well.status == WarpWellStatus.UNRESOLVED_MULTIPLE:
        return f"{base_reason} {well.reason}"
    return base_reason


def _serialize_move_most(
    *,
    draft: ShipOrderDraft,
    ship: ShipObservation,
    result: MoveMostResult,
    warp_well: WarpWellResult | None,
    warp: int,
    speed_multiplier: float,
    warnings: list[str],
) -> dict[str, Any]:
    final_position = (
        warp_well.position
        if warp_well is not None
        else result.position
    )
    certain = result.certain and (
        warp_well.certain if warp_well is not None else True
    )
    return {
        "ship_id": draft.ship_id,
        "movement_mode": "waypoint",
        "phase": "move_most",
        "status": result.status.value,
        "certain": certain,
        "start_x": float(ship.x) if ship.x is not None else None,
        "start_y": float(ship.y) if ship.y is not None else None,
        "waypoint_x": result.waypoint.x if result.waypoint is not None else None,
        "waypoint_y": result.waypoint.y if result.waypoint is not None else None,
        "target_ship_id": None,
        "target_x": None,
        "target_y": None,
        "target_warp": None,
        "target_speed_multiplier": None,
        "target_standard_max_distance": None,
        "pre_well_x": result.position.x if result.position is not None else None,
        "pre_well_y": result.position.y if result.position is not None else None,
        "warp_well_status": (
            warp_well.status.value if warp_well is not None else None
        ),
        "warp_well_planet_id": (
            warp_well.planet_id if warp_well is not None else None
        ),
        "warp_well_planet_name": (
            warp_well.planet_name if warp_well is not None else None
        ),
        "warp_well_pull_distance": (
            warp_well.distance_to_planet if warp_well is not None else None
        ),
        "predicted_x": final_position.x if final_position is not None else None,
        "predicted_y": final_position.y if final_position is not None else None,
        "requested_distance": result.requested_distance,
        "max_distance": result.max_distance,
        "moved_distance": result.moved_distance,
        "displacement_distance": _displacement(ship, final_position),
        "warp": warp,
        "speed_multiplier": speed_multiplier,
        "reason": _warp_well_reason(result.reason, warp_well),
        "warnings": warnings,
    }


def _serialize_intercept(
    *,
    draft: ShipOrderDraft,
    ship: ShipObservation,
    target: ShipObservation | None,
    result: InterceptResult,
    warp_well: WarpWellResult | None,
    warp: int,
    speed_multiplier: float,
    target_warp: int | None,
    target_speed_multiplier: float | None,
    warnings: list[str],
) -> dict[str, Any]:
    target_standard_max_distance = (
        maximum_distance(
            target_warp,
            speed_multiplier=target_speed_multiplier,
        )
        if target_warp is not None and target_speed_multiplier is not None
        else None
    )
    return {
        "ship_id": draft.ship_id,
        "movement_mode": "intercept",
        "phase": "intercept",
        "status": result.status.value,
        "certain": result.certain,
        "start_x": float(ship.x) if ship.x is not None else None,
        "start_y": float(ship.y) if ship.y is not None else None,
        "waypoint_x": None,
        "waypoint_y": None,
        "target_ship_id": draft.intercept_target_ship_id,
        "target_x": float(target.x) if target is not None and target.x is not None else None,
        "target_y": float(target.y) if target is not None and target.y is not None else None,
        "target_warp": target_warp,
        "target_speed_multiplier": target_speed_multiplier,
        "target_standard_max_distance": target_standard_max_distance,
        "pre_well_x": (
            result.pre_final_position.x
            if result.pre_final_position is not None
            else None
        ),
        "pre_well_y": (
            result.pre_final_position.y
            if result.pre_final_position is not None
            else None
        ),
        "warp_well_status": (
            warp_well.status.value if warp_well is not None else None
        ),
        "warp_well_planet_id": (
            warp_well.planet_id if warp_well is not None else None
        ),
        "warp_well_planet_name": (
            warp_well.planet_name if warp_well is not None else None
        ),
        "warp_well_pull_distance": (
            warp_well.distance_to_planet if warp_well is not None else None
        ),
        "predicted_x": result.position.x if result.position is not None else None,
        "predicted_y": result.position.y if result.position is not None else None,
        "requested_distance": result.requested_distance,
        "max_distance": maximum_distance(
            warp,
            speed_multiplier=speed_multiplier,
        ),
        "moved_distance": result.moved_distance,
        "displacement_distance": _displacement(ship, result.position),
        "warp": warp,
        "speed_multiplier": speed_multiplier,
        "reason": _warp_well_reason(result.reason, warp_well),
        "warnings": warnings,
    }


def get_draft_movement_prediction(
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
) -> dict[str, Any]:
    """Predict geometry for saved local movement drafts.

    The current pipeline resolves ordinary Move Most geometry, verified
    planetary warp-well capture, and then Classic/Chained Intercept. It does
    not infer enemy orders or unsupported movement such as Tow/HYP/Chunnel.
    """

    with SessionLocal() as session:
        batch = _latest_batch(
            session,
            user_id=user_id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
        )

        ships = session.execute(
            select(ShipObservation).where(
                ShipObservation.batch_id == batch.id,
            )
        ).scalars().all()
        ships_by_id = {ship.ship_id: ship for ship in ships}

        planets = session.execute(
            select(PlanetObservation).where(
                PlanetObservation.batch_id == batch.id,
                PlanetObservation.x.is_not(None),
                PlanetObservation.y.is_not(None),
            )
        ).scalars().all()

        drafts = session.execute(
            select(ShipOrderDraft)
            .where(
                ShipOrderDraft.user_id == user_id,
                ShipOrderDraft.linked_account_id == linked_account_id,
                ShipOrderDraft.game_id == game_id,
                ShipOrderDraft.turn == turn,
            )
            .order_by(ShipOrderDraft.ship_id)
        ).scalars().all()

        catalog = session.execute(
            select(GameRuleCatalog).where(
                GameRuleCatalog.game_id == game_id,
            )
        ).scalar_one_or_none()
        hull_names = _hull_name_by_id(catalog)
        settings = catalog.settings if catalog is not None else {}
        unlimited_fuel = bool(settings.get("unlimitedfuel", False))
        gravity_wells_enabled = bool(settings.get("gravitywells", True))
        intercept_mode = (
            InterceptMode.CHAINED
            if bool(settings.get("chainedintercept", False))
            else InterceptMode.CLASSIC
        )
        warnings = _common_warnings(unlimited_fuel=unlimited_fuel)

        planet_wells = [
            PlanetWarpWell(
                planet_id=int(planet.planet_id),
                name=planet.name,
                position=Point(float(planet.x), float(planet.y)),
            )
            for planet in planets
            if planet.x is not None and planet.y is not None
        ] if gravity_wells_enabled else []

        def resolve_ship_well(
            *,
            ship_id: int,
            position: Point,
            warp: int,
            moved_distance: float,
        ) -> WarpWellResult | None:
            if not gravity_wells_enabled:
                return None
            return resolve_warp_well(
                ship_id=ship_id,
                pre_well_position=position,
                warp=warp,
                moved_distance=moved_distance,
                planets=planet_wells,
            )

        draft_by_ship_id = {draft.ship_id: draft for draft in drafts}
        speed_by_ship_id: dict[int, float] = {}
        warp_by_ship_id: dict[int, int] = {}
        known_post_move_positions: dict[int, Point] = {}
        items_by_ship_id: dict[int, dict[str, Any]] = {}

        for draft in drafts:
            ship = ships_by_id.get(draft.ship_id)
            if ship is None or ship.x is None or ship.y is None:
                continue

            warp = int(draft.warp if draft.warp is not None else (ship.warp or 0))
            multiplier = _speed_multiplier(ship, hull_names=hull_names)
            warp_by_ship_id[draft.ship_id] = warp
            speed_by_ship_id[draft.ship_id] = multiplier

            if draft.movement_mode != "waypoint":
                continue

            waypoint_x = draft.waypoint_x
            waypoint_y = draft.waypoint_y
            if waypoint_x is None or waypoint_y is None:
                waypoint_x = _payload_int(
                    ship.payload,
                    "waypointx",
                    "targetx",
                    "waypoint_x",
                )
                waypoint_y = _payload_int(
                    ship.payload,
                    "waypointy",
                    "targety",
                    "waypoint_y",
                )

            waypoint = (
                Point(float(waypoint_x), float(waypoint_y))
                if waypoint_x is not None and waypoint_y is not None
                else None
            )
            result = resolve_move_most_order(
                MoveMostOrder(
                    ship_id=draft.ship_id,
                    origin=Point(float(ship.x), float(ship.y)),
                    waypoint=waypoint,
                    warp=warp,
                    speed_multiplier=multiplier,
                )
            )

            warp_well = (
                resolve_ship_well(
                    ship_id=draft.ship_id,
                    position=result.position,
                    warp=warp,
                    moved_distance=float(result.moved_distance or 0.0),
                )
                if result.position is not None
                else None
            )
            final_position = (
                warp_well.position
                if warp_well is not None
                else result.position
            )
            if final_position is not None:
                known_post_move_positions[draft.ship_id] = final_position

            items_by_ship_id[draft.ship_id] = _serialize_move_most(
                draft=draft,
                ship=ship,
                result=result,
                warp_well=warp_well,
                warp=warp,
                speed_multiplier=multiplier,
                warnings=list(warnings),
            )

        intercept_orders: list[InterceptOrder] = []
        for draft in drafts:
            if draft.movement_mode != "intercept":
                continue
            ship = ships_by_id.get(draft.ship_id)
            if ship is None or ship.x is None or ship.y is None:
                continue
            warp = warp_by_ship_id.get(
                draft.ship_id,
                int(draft.warp if draft.warp is not None else (ship.warp or 0)),
            )
            multiplier = speed_by_ship_id.get(
                draft.ship_id,
                _speed_multiplier(ship, hull_names=hull_names),
            )
            warp_by_ship_id[draft.ship_id] = warp
            speed_by_ship_id[draft.ship_id] = multiplier

            def post_move_transform(
                position: Point,
                moved_distance: float,
                *,
                ship_id: int = draft.ship_id,
                ship_warp: int = warp,
            ) -> Point | None:
                well = resolve_ship_well(
                    ship_id=ship_id,
                    position=position,
                    warp=ship_warp,
                    moved_distance=moved_distance,
                )
                return well.position if well is not None else position

            intercept_orders.append(
                InterceptOrder(
                    ship_id=draft.ship_id,
                    origin=Point(float(ship.x), float(ship.y)),
                    target_ship_id=draft.intercept_target_ship_id,
                    max_distance=maximum_distance(
                        warp,
                        speed_multiplier=multiplier,
                    ),
                    target_visible=(
                        draft.intercept_target_ship_id in ships_by_id
                        if draft.intercept_target_ship_id is not None
                        else False
                    ),
                    post_move_transform=post_move_transform,
                )
            )

        if intercept_orders:
            intercept_results = resolve_intercepts(
                intercept_orders,
                prior_final_positions=known_post_move_positions,
                mode=intercept_mode,
            )
            for order in intercept_orders:
                draft = draft_by_ship_id[order.ship_id]
                ship = ships_by_id[order.ship_id]
                target = (
                    ships_by_id.get(draft.intercept_target_ship_id)
                    if draft.intercept_target_ship_id is not None
                    else None
                )
                target_warp = (
                    int(target.warp)
                    if target is not None and target.warp is not None
                    else None
                )
                target_speed_multiplier = (
                    _speed_multiplier(target, hull_names=hull_names)
                    if target is not None
                    else None
                )
                intercept_result = intercept_results[order.ship_id]
                intercept_well = (
                    resolve_ship_well(
                        ship_id=order.ship_id,
                        position=intercept_result.pre_final_position,
                        warp=warp_by_ship_id[order.ship_id],
                        moved_distance=float(intercept_result.moved_distance or 0.0),
                    )
                    if intercept_result.pre_final_position is not None
                    else None
                )
                items_by_ship_id[order.ship_id] = _serialize_intercept(
                    draft=draft,
                    ship=ship,
                    target=target,
                    result=intercept_result,
                    warp_well=intercept_well,
                    warp=warp_by_ship_id[order.ship_id],
                    speed_multiplier=speed_by_ship_id[order.ship_id],
                    target_warp=target_warp,
                    target_speed_multiplier=target_speed_multiplier,
                    warnings=list(warnings),
                )

        return {
            "game_id": game_id,
            "linked_account_id": linked_account_id,
            "turn": turn,
            "intercept_mode": intercept_mode.value,
            "basis": "local_order_drafts_geometry",
            "host_final": False,
            "items": [
                items_by_ship_id[ship_id]
                for ship_id in sorted(items_by_ship_id)
            ],
        }
