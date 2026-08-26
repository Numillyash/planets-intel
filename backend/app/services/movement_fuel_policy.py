from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import hypot
from typing import Any, Mapping, Sequence

from app.services.movement_fuel import (
    MovementMassEvidence,
    engine_fuel_factor,
    movement_fuel_use,
    movement_mass_from_private_ship,
    project_toward_waypoint,
    prorate_waypoint_distance,
)


class WaypointFuelStatus(StrEnum):
    UNLIMITED = "unlimited"
    NOT_REQUIRED = "not_required"
    SUFFICIENT = "sufficient"
    LIMITED = "limited"
    UNKNOWN = "unknown"
    UNSUPPORTED_ZERO_FUEL = "unsupported_zero_fuel"
    UNSUPPORTED_PARTIAL_WAYPOINT = "unsupported_partial_waypoint"
    UNSUPPORTED_GRAVITONIC = "unsupported_gravitonic"


@dataclass(frozen=True, slots=True)
class WaypointFuelResolution:
    status: WaypointFuelStatus
    movement_mass: int | None
    fuel_available: int | None
    fuel_factor: int | None
    fuel_required: int | None
    fuel_used: int | None
    fuel_limited: bool | None
    override_x: int | None
    override_y: int | None
    override_moved_distance: float | None
    certain: bool
    reason: str
    mass_reason: str | None = None

    @property
    def has_position_override(self) -> bool:
        return self.override_x is not None and self.override_y is not None


def _base(
    *,
    status: WaypointFuelStatus,
    evidence: MovementMassEvidence | None,
    fuel_factor: int | None,
    fuel_required: int | None,
    fuel_used: int | None,
    fuel_limited: bool | None,
    certain: bool,
    reason: str,
    override_x: int | None = None,
    override_y: int | None = None,
    override_moved_distance: float | None = None,
) -> WaypointFuelResolution:
    return WaypointFuelResolution(
        status=status,
        movement_mass=evidence.total_mass if evidence is not None else None,
        fuel_available=evidence.fuel_available if evidence is not None else None,
        fuel_factor=fuel_factor,
        fuel_required=fuel_required,
        fuel_used=fuel_used,
        fuel_limited=fuel_limited,
        override_x=override_x,
        override_y=override_y,
        override_moved_distance=override_moved_distance,
        certain=certain,
        reason=reason,
        mass_reason=evidence.reason if evidence is not None else None,
    )


def resolve_waypoint_fuel(
    *,
    unlimited_fuel: bool,
    payload: Mapping[str, Any],
    hull_id: int | None,
    owner_observed: bool,
    hulls: Sequence[Mapping[str, Any]],
    beams: Sequence[Mapping[str, Any]],
    torpedoes: Sequence[Mapping[str, Any]],
    engines: Sequence[Mapping[str, Any]],
    warp: int,
    speed_multiplier: float,
    origin_x: int,
    origin_y: int,
    target_x: int | None,
    target_y: int | None,
    requested_distance: float | None,
    geometric_moved_distance: float | None,
    geometric_max_distance: float,
) -> WaypointFuelResolution:
    """Resolve the verified production subset of normal waypoint fuel.

    Sufficient-fuel arithmetic is documented. Positive insufficient fuel is
    applied only to the differential-verified subset: a reachable, normal-speed
    waypoint. Zero-fuel movement, shortage on a partial waypoint and shortage
    on a Gravitonic move remain fail-closed until separately validated.
    """

    if unlimited_fuel:
        return _base(
            status=WaypointFuelStatus.UNLIMITED,
            evidence=None,
            fuel_factor=None,
            fuel_required=None,
            fuel_used=None,
            fuel_limited=False,
            certain=True,
            reason="Game rules provide unlimited movement fuel.",
        )

    if (
        target_x is None
        or target_y is None
        or requested_distance is None
        or geometric_moved_distance is None
        or requested_distance <= 0
        or geometric_moved_distance <= 0
        or warp <= 0
    ):
        return _base(
            status=WaypointFuelStatus.NOT_REQUIRED,
            evidence=None,
            fuel_factor=0 if warp <= 0 else None,
            fuel_required=0,
            fuel_used=0,
            fuel_limited=False,
            certain=True,
            reason="This draft has no positive ordinary movement distance requiring fuel.",
        )

    evidence = movement_mass_from_private_ship(
        payload=payload,
        hull_id=hull_id,
        owner_observed=owner_observed,
        hulls=hulls,
        beams=beams,
        torpedoes=torpedoes,
    )
    if not evidence.available or evidence.total_mass is None or evidence.fuel_available is None:
        return _base(
            status=WaypointFuelStatus.UNKNOWN,
            evidence=evidence,
            fuel_factor=None,
            fuel_required=None,
            fuel_used=None,
            fuel_limited=None,
            certain=False,
            reason="Fuel-limited endpoint cannot be resolved because factual movement mass is incomplete.",
        )

    fuel_factor = engine_fuel_factor(
        engine_id=evidence.engine_id,
        warp=warp,
        engines=engines,
    )
    if fuel_factor is None:
        return _base(
            status=WaypointFuelStatus.UNKNOWN,
            evidence=evidence,
            fuel_factor=None,
            fuel_required=None,
            fuel_used=None,
            fuel_limited=None,
            certain=False,
            reason="Fuel-limited endpoint cannot be resolved because the engine fuel factor is unknown.",
        )

    fuel_required = movement_fuel_use(
        fuel_factor=fuel_factor,
        total_mass=evidence.total_mass,
        distance_traveled=geometric_moved_distance,
        max_distance_per_turn=geometric_max_distance,
    )
    fuel_available = evidence.fuel_available

    if fuel_required <= fuel_available:
        return _base(
            status=WaypointFuelStatus.SUFFICIENT,
            evidence=evidence,
            fuel_factor=fuel_factor,
            fuel_required=fuel_required,
            fuel_used=fuel_required,
            fuel_limited=False,
            certain=True,
            reason="Current factual fuel is sufficient for the geometric Move Most endpoint.",
        )

    if fuel_available == 0:
        return _base(
            status=WaypointFuelStatus.UNSUPPORTED_ZERO_FUEL,
            evidence=evidence,
            fuel_factor=fuel_factor,
            fuel_required=fuel_required,
            fuel_used=None,
            fuel_limited=True,
            certain=False,
            reason="Zero-fuel movement is a separate Host mechanic and is not yet predicted.",
        )

    if requested_distance > geometric_max_distance + 1e-9:
        return _base(
            status=WaypointFuelStatus.UNSUPPORTED_PARTIAL_WAYPOINT,
            evidence=evidence,
            fuel_factor=fuel_factor,
            fuel_required=fuel_required,
            fuel_used=None,
            fuel_limited=True,
            certain=False,
            reason="Insufficient-fuel proration for a waypoint already beyond one-turn range is not yet validated.",
        )

    if abs(speed_multiplier - 1.0) > 1e-9:
        return _base(
            status=WaypointFuelStatus.UNSUPPORTED_GRAVITONIC,
            evidence=evidence,
            fuel_factor=fuel_factor,
            fuel_required=fuel_required,
            fuel_used=None,
            fuel_limited=True,
            certain=False,
            reason="Insufficient-fuel proration for Gravitonic movement is not yet validated in production.",
        )

    proration = prorate_waypoint_distance(
        requested_distance=requested_distance,
        fuel_available=fuel_available,
        fuel_required=fuel_required,
    )
    destination_x, destination_y = project_toward_waypoint(
        x=origin_x,
        y=origin_y,
        target_x=target_x,
        target_y=target_y,
        distance=proration.distance,
    )
    actual_distance = hypot(destination_x - origin_x, destination_y - origin_y)
    return _base(
        status=WaypointFuelStatus.LIMITED,
        evidence=evidence,
        fuel_factor=fuel_factor,
        fuel_required=fuel_required,
        fuel_used=fuel_available,
        fuel_limited=True,
        certain=True,
        reason=(
            "Positive insufficient fuel applies the verified Nu waypoint-distance "
            "proration and Host major/minor-axis projection."
        ),
        override_x=destination_x,
        override_y=destination_y,
        override_moved_distance=actual_distance,
    )
