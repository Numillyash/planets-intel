from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math

from app.services.movement_intercept import Point


WARP_WELL_RADIUS = 3.0
_EPSILON = 1e-9


class WarpWellStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    OUTSIDE_WELLS = "outside_wells"
    CAPTURED = "captured"
    UNRESOLVED_MULTIPLE = "unresolved_multiple"


@dataclass(frozen=True, slots=True)
class PlanetWarpWell:
    planet_id: int
    position: Point
    name: str | None = None


@dataclass(frozen=True, slots=True)
class WarpWellResult:
    ship_id: int
    status: WarpWellStatus
    pre_well_position: Point
    position: Point | None
    planet_id: int | None
    planet_name: str | None
    distance_to_planet: float | None
    certain: bool
    reason: str


def _distance(left: Point, right: Point) -> float:
    return math.hypot(right.x - left.x, right.y - left.y)


def resolve_warp_well(
    *,
    ship_id: int,
    pre_well_position: Point,
    warp: int,
    moved_distance: float,
    planets: list[PlanetWarpWell],
) -> WarpWellResult:
    """Resolve normal-movement planetary warp-well capture.

    Verified Nu behavior modelled here:
    - ordinary ships that actually moved at Warp > 1 are pulled into orbit when
      their end-of-movement point is within 3 ly of a planet;
    - Warp 0/1 and non-moving ships are unaffected;
    - this resolver is for ordinary movement only. Hyperjump has a different
      exactly-3-ly boundary rule and is deliberately handled elsewhere.

    The public documentation does not define a tie-break for a point lying in
    more than one planetary warp well. Such a case therefore remains
    unresolved rather than inventing a planet-selection rule.
    """

    if warp < 0 or warp > 9:
        raise ValueError("warp must be between 0 and 9")
    if moved_distance < 0:
        raise ValueError("moved_distance must be non-negative")

    if warp <= 1 or moved_distance <= _EPSILON:
        return WarpWellResult(
            ship_id=ship_id,
            status=WarpWellStatus.NOT_APPLICABLE,
            pre_well_position=pre_well_position,
            position=pre_well_position,
            planet_id=None,
            planet_name=None,
            distance_to_planet=None,
            certain=True,
            reason=(
                "Planetary warp wells do not pull non-moving ships or ships "
                "travelling at Warp 1."
            ),
        )

    candidates: list[tuple[PlanetWarpWell, float]] = []
    for planet in planets:
        distance = _distance(pre_well_position, planet.position)
        if distance <= WARP_WELL_RADIUS + _EPSILON:
            candidates.append((planet, distance))

    if not candidates:
        return WarpWellResult(
            ship_id=ship_id,
            status=WarpWellStatus.OUTSIDE_WELLS,
            pre_well_position=pre_well_position,
            position=pre_well_position,
            planet_id=None,
            planet_name=None,
            distance_to_planet=None,
            certain=True,
            reason="The end-of-movement point is outside every planetary warp well.",
        )

    if len(candidates) > 1:
        return WarpWellResult(
            ship_id=ship_id,
            status=WarpWellStatus.UNRESOLVED_MULTIPLE,
            pre_well_position=pre_well_position,
            position=None,
            planet_id=None,
            planet_name=None,
            distance_to_planet=None,
            certain=False,
            reason=(
                "The end-of-movement point lies in multiple planetary warp wells; "
                "the authoritative tie-break is not modelled."
            ),
        )

    planet, distance = candidates[0]
    return WarpWellResult(
        ship_id=ship_id,
        status=WarpWellStatus.CAPTURED,
        pre_well_position=pre_well_position,
        position=planet.position,
        planet_id=planet.planet_id,
        planet_name=planet.name,
        distance_to_planet=distance,
        certain=True,
        reason="The ship ends ordinary movement inside a planetary warp well and falls into orbit.",
    )
