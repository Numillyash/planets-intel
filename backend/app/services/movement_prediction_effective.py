from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.planet_observation import PlanetObservation
from app.models.ship_observation import ShipObservation
from app.models.ship_order_draft import ShipOrderDraft
from app.services import movement_prediction as _implementation
from app.services import movement_prediction_runtime as _runtime
from app.services.movement_prediction_blockers import annotate_prediction_blocker
from app.services.movement_prediction_unified_runtime import (
    MovementPredictionAccessError,
    MovementPredictionNotFound,
    get_draft_movement_prediction as _get_draft_movement_prediction,
)
from app.services.movement_warp_well import PlanetWarpWell
from app.services.movement_intercept import Point


def _serialize_missing_tow_item(
    *,
    ship: ShipObservation,
    outcome: _runtime._TowRuntimeOutcome,
    context: _runtime._FuelContext,
) -> dict[str, Any]:
    warnings = _runtime._common_warnings(
        unlimited_fuel=context.unlimited_fuel,
    )
    warnings.append(
        "This Tow prediction is emitted from the factual upstream order even though no local order-draft row exists for this ship."
    )

    result: dict[str, Any] = {
        "ship_id": int(ship.ship_id),
        "movement_mode": "tow",
        "phase": "tow",
        "status": outcome.status,
        "certain": outcome.certain,
        "start_x": float(ship.x) if ship.x is not None else None,
        "start_y": float(ship.y) if ship.y is not None else None,
        "waypoint_x": outcome.waypoint.x if outcome.waypoint is not None else None,
        "waypoint_y": outcome.waypoint.y if outcome.waypoint is not None else None,
        "target_ship_id": None,
        "target_x": None,
        "target_y": None,
        "target_warp": None,
        "target_speed_multiplier": None,
        "target_standard_max_distance": None,
        "pre_well_x": outcome.pre_well_position.x if outcome.pre_well_position is not None else None,
        "pre_well_y": outcome.pre_well_position.y if outcome.pre_well_position is not None else None,
        "warp_well_status": None,
        "warp_well_planet_id": None,
        "warp_well_planet_name": None,
        "warp_well_pull_distance": None,
        "predicted_x": outcome.position.x if outcome.position is not None else None,
        "predicted_y": outcome.position.y if outcome.position is not None else None,
        "requested_distance": outcome.requested_distance,
        "max_distance": outcome.max_distance,
        "moved_distance": outcome.moved_distance,
        "displacement_distance": _implementation._displacement(ship, outcome.position),
        "warp": outcome.route_warp,
        "speed_multiplier": outcome.route_speed_multiplier if outcome.route_speed_multiplier is not None else 1.0,
        "reason": outcome.reason,
        "warnings": warnings,
    }
    result = _runtime._apply_tow_metadata(
        result,
        outcome=outcome,
        context=context,
    )
    return annotate_prediction_blocker(result)


def _append_missing_tow_items(
    result: Mapping[str, Any],
    *,
    ships: list[ShipObservation],
    drafts: list[ShipOrderDraft],
    catalog: GameRuleCatalog | None,
    planets: list[PlanetObservation],
    owner_slot_id: int,
) -> dict[str, Any]:
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
    ] if gravity_wells_enabled else []

    tow_outcomes, tow_known_positions = _runtime._build_tow_outcomes(
        ships=ships,
        drafts=drafts,
        owner_slot_id=owner_slot_id,
        hulls=hulls,
        hull_names=hull_names,
        unlimited_fuel=unlimited_fuel,
        gravity_wells_enabled=gravity_wells_enabled,
        planet_wells=planet_wells,
    )
    if not tow_outcomes:
        return dict(result)

    ships_by_id = {int(ship.ship_id): ship for ship in ships}
    context = _runtime._FuelContext(
        owner_slot_id=owner_slot_id,
        unlimited_fuel=unlimited_fuel,
        ships=ships_by_id,
        hulls=hulls,
        beams=list(catalog.beams) if catalog is not None else [],
        torpedoes=list(catalog.torpedos) if catalog is not None else [],
        engines=list(catalog.engines) if catalog is not None else [],
        tow_outcomes=tow_outcomes,
        tow_known_positions=tow_known_positions,
    )

    items = list(result.get("items") or [])
    existing_ship_ids = {
        int(item["ship_id"])
        for item in items
        if isinstance(item, Mapping) and isinstance(item.get("ship_id"), int)
    }

    for ship_id, outcome in sorted(tow_outcomes.items()):
        if ship_id in existing_ship_ids:
            continue
        ship = ships_by_id.get(ship_id)
        if ship is None:
            continue
        items.append(
            _serialize_missing_tow_item(
                ship=ship,
                outcome=outcome,
                context=context,
            )
        )

    output = dict(result)
    output["items"] = sorted(
        items,
        key=lambda item: int(item.get("ship_id", 0)) if isinstance(item, Mapping) else 0,
    )
    return output


def get_effective_movement_prediction(
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
) -> dict[str, Any]:
    result = _get_draft_movement_prediction(
        user_id=user_id,
        linked_account_id=linked_account_id,
        game_id=game_id,
        turn=turn,
    )

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

    return _append_missing_tow_items(
        result,
        ships=ships,
        drafts=drafts,
        catalog=catalog,
        planets=planets,
        owner_slot_id=int(batch.source_player_slot_id),
    )


__all__ = [
    "MovementPredictionAccessError",
    "MovementPredictionNotFound",
    "get_effective_movement_prediction",
]
