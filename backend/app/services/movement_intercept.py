from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Callable, Mapping


class InterceptMode(StrEnum):
    CLASSIC = "classic"
    CHAINED = "chained"


class InterceptStatus(StrEnum):
    MOVED = "moved"
    REACHED_TARGET = "reached_target"
    STAYED_NO_SPEED = "stayed_no_speed"
    FAILED_INVALID_TARGET = "failed_invalid_target"
    UNRESOLVED_CHAINED_CYCLE = "unresolved_chained_cycle"
    UNRESOLVED_TARGET = "unresolved_target"
    UNRESOLVED_POST_MOVE = "unresolved_post_move"


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


PostMoveTransform = Callable[[Point, float], Point | None]


@dataclass(frozen=True, slots=True)
class InterceptOrder:
    """Input for one ship during the Intercept movement phase.

    ``origin`` is the ship position before the Intercept phase. ``max_distance``
    is deliberately supplied by the caller: engine, gravitonic, fuel, tow and
    other movement rules belong to the wider movement engine and must not be
    guessed here.

    ``target_visible`` represents whether this interceptor still has a valid
    target lock under the factual turn state. An invalid/hidden target makes an
    Intercept mission fail without falling back to the normal waypoint.

    ``post_move_transform`` represents deterministic movement substeps that
    finalize the ship's position after geometric Intercept movement. Planetary
    warp-well capture is one such Host substep. Keeping it here is important for
    Chained Intercept: a later interceptor must pursue the target's finalized
    position, not its pre-warp-well geometric endpoint.
    """

    ship_id: int
    origin: Point
    target_ship_id: int | None
    max_distance: float
    target_visible: bool = True
    post_move_transform: PostMoveTransform | None = None


@dataclass(frozen=True, slots=True)
class InterceptResult:
    ship_id: int
    status: InterceptStatus
    position: Point | None
    target_ship_id: int | None
    target_position: Point | None
    requested_distance: float | None
    moved_distance: float | None
    certain: bool
    reason: str
    pre_final_position: Point | None = None


def _distance(left: Point, right: Point) -> float:
    return math.hypot(right.x - left.x, right.y - left.y)


def _move_toward(
    origin: Point,
    target: Point,
    max_distance: float,
) -> tuple[Point, float, float, bool]:
    requested = _distance(origin, target)
    available = max(float(max_distance), 0.0)

    if requested == 0.0 or available == 0.0:
        return origin, requested, 0.0, requested == 0.0

    if requested <= available:
        return target, requested, requested, True

    ratio = available / requested
    position = Point(
        x=origin.x + (target.x - origin.x) * ratio,
        y=origin.y + (target.y - origin.y) * ratio,
    )
    return position, requested, available, False


def _invalid_target_result(
    order: InterceptOrder,
    reason: str,
) -> InterceptResult:
    return InterceptResult(
        ship_id=order.ship_id,
        status=InterceptStatus.FAILED_INVALID_TARGET,
        position=order.origin,
        target_ship_id=order.target_ship_id,
        target_position=None,
        requested_distance=None,
        moved_distance=0.0,
        certain=True,
        reason=reason,
        pre_final_position=order.origin,
    )


def _unresolved_target_result(
    order: InterceptOrder,
    reason: str,
) -> InterceptResult:
    return InterceptResult(
        ship_id=order.ship_id,
        status=InterceptStatus.UNRESOLVED_TARGET,
        position=None,
        target_ship_id=order.target_ship_id,
        target_position=None,
        requested_distance=None,
        moved_distance=None,
        certain=False,
        reason=reason,
        pre_final_position=None,
    )


def _movement_result(
    order: InterceptOrder,
    target_position: Point,
) -> InterceptResult:
    pre_final_position, requested, moved, reached = _move_toward(
        order.origin,
        target_position,
        order.max_distance,
    )

    if moved == 0.0 and not reached:
        status = InterceptStatus.STAYED_NO_SPEED
        reason = "Valid intercept target, but available movement distance is zero."
    elif reached:
        status = InterceptStatus.REACHED_TARGET
        reason = "Interceptor can reach the target position during this phase."
    else:
        status = InterceptStatus.MOVED
        reason = "Interceptor moves toward the target but cannot reach it this turn."

    position: Point | None = pre_final_position
    certain = True
    if order.post_move_transform is not None:
        position = order.post_move_transform(pre_final_position, moved)
        if position is None:
            status = InterceptStatus.UNRESOLVED_POST_MOVE
            certain = False
            reason = (
                "Geometric Intercept movement is known, but a post-movement "
                "Host substep could not be resolved safely."
            )

    return InterceptResult(
        ship_id=order.ship_id,
        status=status,
        position=position,
        target_ship_id=order.target_ship_id,
        target_position=target_position,
        requested_distance=requested,
        moved_distance=moved,
        certain=certain,
        reason=reason,
        pre_final_position=pre_final_position,
    )


def resolve_classic_intercepts(
    orders: list[InterceptOrder],
    *,
    prior_final_positions: Mapping[int, Point],
) -> dict[int, InterceptResult]:
    """Resolve Classic Intercept in ascending Ship ID order.

    ``prior_final_positions`` must contain ships whose position after Tow/Move
    Most is actually known. Interceptors are seeded at their own origins and
    then updated one-by-one. Missing post-Move-Most target positions remain
    unresolved rather than being misclassified as invalid target locks.
    """

    orders_by_id = {order.ship_id: order for order in orders}
    positions: dict[int, Point] = dict(prior_final_positions)
    for order in orders:
        positions[order.ship_id] = order.origin

    results: dict[int, InterceptResult] = {}

    for ship_id in sorted(orders_by_id):
        order = orders_by_id[ship_id]

        if order.target_ship_id is None:
            result = _invalid_target_result(order, "No intercept target is selected.")
        elif order.target_ship_id == ship_id:
            result = _invalid_target_result(order, "A ship cannot intercept itself.")
        elif not order.target_visible:
            result = _invalid_target_result(
                order,
                "Intercept target is not valid/visible at the start of the turn.",
            )
        else:
            target_position = positions.get(order.target_ship_id)
            if target_position is None:
                result = _unresolved_target_result(
                    order,
                    "Intercept target is visible, but its post-Move-Most position is not known.",
                )
            else:
                result = _movement_result(order, target_position)

        results[ship_id] = result
        if result.position is not None:
            positions[ship_id] = result.position

    return results


def resolve_chained_intercepts(
    orders: list[InterceptOrder],
    *,
    prior_final_positions: Mapping[int, Point],
) -> dict[int, InterceptResult]:
    """Resolve the deterministic acyclic portion of Chained Intercept.

    Chained Intercept waits for an intercepting target to resolve before its
    pursuer moves. Valid dependency chains are therefore deterministic here.
    ``post_move_transform`` is applied before a result becomes available to a
    pursuer, matching Host substeps such as planetary warp-well capture.

    Pure valid loops require NuHost's agility/tie-breaking calculation. The
    public rules describe the factors but not a complete reproducible formula,
    so this module intentionally marks such loops as unresolved rather than
    inventing a result.
    """

    orders_by_id = {order.ship_id: order for order in orders}
    results: dict[int, InterceptResult] = {}
    visiting: list[int] = []
    visiting_set: set[int] = set()

    def resolve(ship_id: int) -> InterceptResult:
        existing = results.get(ship_id)
        if existing is not None:
            return existing

        order = orders_by_id[ship_id]

        if order.target_ship_id is None:
            result = _invalid_target_result(order, "No intercept target is selected.")
            results[ship_id] = result
            return result

        if order.target_ship_id == ship_id:
            result = _invalid_target_result(order, "A ship cannot intercept itself.")
            results[ship_id] = result
            return result

        if not order.target_visible:
            result = _invalid_target_result(
                order,
                "Intercept target is not valid/visible at the start of the turn.",
            )
            results[ship_id] = result
            return result

        if ship_id in visiting_set:
            cycle_start = visiting.index(ship_id)
            cycle_ids = visiting[cycle_start:]
            for cycle_id in cycle_ids:
                cycle_order = orders_by_id[cycle_id]
                results[cycle_id] = InterceptResult(
                    ship_id=cycle_id,
                    status=InterceptStatus.UNRESOLVED_CHAINED_CYCLE,
                    position=None,
                    target_ship_id=cycle_order.target_ship_id,
                    target_position=None,
                    requested_distance=None,
                    moved_distance=None,
                    certain=False,
                    reason=(
                        "Valid Chained Intercept loop requires NuHost agility "
                        "tie-breaking, which is not yet modeled."
                    ),
                    pre_final_position=None,
                )
            return results[ship_id]

        visiting.append(ship_id)
        visiting_set.add(ship_id)
        try:
            target_id = order.target_ship_id
            if target_id in orders_by_id:
                target_result = resolve(target_id)
                if target_result.position is None:
                    if ship_id in results:
                        return results[ship_id]
                    result = _unresolved_target_result(
                        order,
                        "Intercept target final position is unresolved, so this chained interceptor cannot be predicted safely.",
                    )
                else:
                    result = _movement_result(order, target_result.position)
            else:
                target_position = prior_final_positions.get(target_id)
                if target_position is None:
                    result = _unresolved_target_result(
                        order,
                        "Intercept target is visible, but its post-Move-Most position is not known.",
                    )
                else:
                    result = _movement_result(order, target_position)

            if ship_id not in results:
                results[ship_id] = result
            return results[ship_id]
        finally:
            if visiting and visiting[-1] == ship_id:
                visiting.pop()
            else:
                visiting[:] = [item for item in visiting if item != ship_id]
            visiting_set.discard(ship_id)

    for ship_id in sorted(orders_by_id):
        resolve(ship_id)

    return results


def resolve_intercepts(
    orders: list[InterceptOrder],
    *,
    prior_final_positions: Mapping[int, Point],
    mode: InterceptMode,
) -> dict[int, InterceptResult]:
    if mode == InterceptMode.CLASSIC:
        return resolve_classic_intercepts(
            orders,
            prior_final_positions=prior_final_positions,
        )

    if mode == InterceptMode.CHAINED:
        return resolve_chained_intercepts(
            orders,
            prior_final_positions=prior_final_positions,
        )

    raise ValueError(f"Unsupported intercept mode: {mode!r}")
