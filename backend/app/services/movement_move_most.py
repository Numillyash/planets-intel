from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math

from app.services.movement_intercept import Point


class MoveMostStatus(StrEnum):
    MOVED = "moved"
    REACHED_WAYPOINT = "reached_waypoint"
    STAYED_NO_SPEED = "stayed_no_speed"
    STAYED_NO_WAYPOINT = "stayed_no_waypoint"
    STAYED_AT_WAYPOINT = "stayed_at_waypoint"
    UNRESOLVED_INELIGIBLE = "unresolved_ineligible"


@dataclass(frozen=True, slots=True)
class MoveMostOrder:
    """Geometry input for one ship in the Move Most phase.

    This layer intentionally models only the deterministic kinematic part of
    normal movement. ``speed_multiplier`` captures verified travel-rate
    modifiers such as the Gravitonic Accelerator (2x). Fuel, towing,
    hyperjumping, warp wells, mine hits, star-cluster effects and other Host
    substeps belong to later movement layers and are not guessed here.
    """

    ship_id: int
    origin: Point
    waypoint: Point | None
    warp: int
    speed_multiplier: float = 1.0
    eligible: bool = True
    ineligible_reason: str | None = None


@dataclass(frozen=True, slots=True)
class MoveMostResult:
    ship_id: int
    status: MoveMostStatus
    position: Point | None
    waypoint: Point | None
    requested_distance: float | None
    max_distance: float
    moved_distance: float | None
    reached_waypoint: bool | None
    certain: bool
    reason: str


def maximum_distance(warp: int, *, speed_multiplier: float = 1.0) -> float:
    """Return the verified geometric maximum travel distance for one turn."""

    if warp < 0 or warp > 9:
        raise ValueError("warp must be between 0 and 9")
    if speed_multiplier <= 0:
        raise ValueError("speed_multiplier must be positive")
    return float(warp * warp) * float(speed_multiplier)


def _distance(left: Point, right: Point) -> float:
    return math.hypot(right.x - left.x, right.y - left.y)


def _move_toward(
    origin: Point,
    target: Point,
    max_distance: float,
) -> tuple[Point, float, float, bool]:
    requested = _distance(origin, target)
    available = max(float(max_distance), 0.0)

    if requested == 0.0:
        return origin, requested, 0.0, True
    if available == 0.0:
        return origin, requested, 0.0, False
    if requested <= available:
        return target, requested, requested, True

    ratio = available / requested
    return (
        Point(
            x=origin.x + (target.x - origin.x) * ratio,
            y=origin.y + (target.y - origin.y) * ratio,
        ),
        requested,
        available,
        False,
    )


def resolve_move_most_order(order: MoveMostOrder) -> MoveMostResult:
    max_distance = maximum_distance(
        order.warp,
        speed_multiplier=order.speed_multiplier,
    )

    if not order.eligible:
        return MoveMostResult(
            ship_id=order.ship_id,
            status=MoveMostStatus.UNRESOLVED_INELIGIBLE,
            position=None,
            waypoint=order.waypoint,
            requested_distance=None,
            max_distance=max_distance,
            moved_distance=None,
            reached_waypoint=None,
            certain=False,
            reason=order.ineligible_reason or (
                "Ship is not eligible for ordinary Move Most prediction."
            ),
        )

    if order.waypoint is None:
        return MoveMostResult(
            ship_id=order.ship_id,
            status=MoveMostStatus.STAYED_NO_WAYPOINT,
            position=order.origin,
            waypoint=None,
            requested_distance=None,
            max_distance=max_distance,
            moved_distance=0.0,
            reached_waypoint=False,
            certain=True,
            reason="No waypoint is selected, so the ship remains at its origin.",
        )

    requested = _distance(order.origin, order.waypoint)
    if requested == 0.0:
        return MoveMostResult(
            ship_id=order.ship_id,
            status=MoveMostStatus.STAYED_AT_WAYPOINT,
            position=order.origin,
            waypoint=order.waypoint,
            requested_distance=0.0,
            max_distance=max_distance,
            moved_distance=0.0,
            reached_waypoint=True,
            certain=True,
            reason="The waypoint is already at the ship's current position.",
        )

    if max_distance == 0.0:
        return MoveMostResult(
            ship_id=order.ship_id,
            status=MoveMostStatus.STAYED_NO_SPEED,
            position=order.origin,
            waypoint=order.waypoint,
            requested_distance=requested,
            max_distance=0.0,
            moved_distance=0.0,
            reached_waypoint=False,
            certain=True,
            reason="Warp 0 provides no ordinary Move Most travel distance.",
        )

    position, requested, moved, reached = _move_toward(
        order.origin,
        order.waypoint,
        max_distance,
    )
    return MoveMostResult(
        ship_id=order.ship_id,
        status=(
            MoveMostStatus.REACHED_WAYPOINT
            if reached
            else MoveMostStatus.MOVED
        ),
        position=position,
        waypoint=order.waypoint,
        requested_distance=requested,
        max_distance=max_distance,
        moved_distance=moved,
        reached_waypoint=reached,
        certain=True,
        reason=(
            "The waypoint is reachable within this Move Most phase."
            if reached
            else "The ship moves its maximum geometric distance toward the waypoint."
        ),
    )


def resolve_move_most(
    orders: list[MoveMostOrder],
) -> dict[int, MoveMostResult]:
    """Resolve independent ordinary Move Most orders by Ship ID."""

    return {
        order.ship_id: resolve_move_most_order(order)
        for order in sorted(orders, key=lambda item: item.ship_id)
    }
