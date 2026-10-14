from __future__ import annotations

from contextvars import ContextVar
from dataclasses import replace
from typing import Any, Mapping

from app.services import movement_prediction_runtime as _runtime
from app.services import movement_prediction as _implementation
from app.services.movement_intercept import (
    InterceptMode,
    InterceptOrder,
    InterceptResult,
    InterceptStatus,
    Point,
)
from app.services.movement_prediction_blockers import annotate_prediction_blocker
from app.services.movement_turn_state import MovementPhase, MovementTurnState


# The finite-fuel Intercept formula is supported by historical differential
# evidence in planets-lab. Production still fails closed because the current
# private snapshot is not automatically the factual fuel state at the Intercept
# Host phase, especially when earlier movement phases may have changed it.
_FINITE_INTERCEPT_REASON = (
    "Finite-fuel Intercept endpoint is withheld because a phase-aligned "
    "Intercept fuel state is unavailable; snapshot neutronium is not "
    "automatically Intercept-phase fuel."
)

_TURN_STATE: ContextVar[MovementTurnState | None] = ContextVar(
    "movement_prediction_turn_state",
    default=None,
)

# Importing movement_prediction_runtime installs the verified Tow/Move-Most
# facade first. We extend that facade rather than bypassing it.
_PREVIOUS_RESOLVE_INTERCEPTS = _implementation.resolve_intercepts
_PREVIOUS_SERIALIZE_INTERCEPT = _implementation._serialize_intercept


def _sync_prior_state(
    state: MovementTurnState,
    *,
    prior_final_positions: Mapping[int, Point],
) -> None:
    state.merge_known(
        prior_final_positions,
        phase=MovementPhase.MOVE_MOST,
        reason="Known post-Tow/Move-Most position supplied to Intercept.",
    )

    context = _runtime._CONTEXT.get()
    if context is None:
        return

    for ship_id, outcome in context.tow_outcomes.items():
        if outcome.certain and outcome.position is not None:
            state.set_known(
                ship_id,
                outcome.position,
                phase=MovementPhase.TOW,
                reason=outcome.reason,
            )
        else:
            state.set_unresolved(
                ship_id,
                phase=MovementPhase.TOW,
                reason=outcome.reason,
            )

    for ship_id, fuel in context.resolutions.items():
        if fuel.certain:
            continue
        # Tow has earlier phase precedence and already records why the ship is
        # unavailable to later movement.
        existing = state.get(ship_id)
        if existing is not None and existing.phase == MovementPhase.TOW:
            continue
        state.set_unresolved(
            ship_id,
            phase=MovementPhase.MOVE_MOST,
            reason=f"Move Most fuel endpoint unresolved: {fuel.reason}",
        )


def _finite_intercept_needs_fail_closed(
    order: InterceptOrder,
    result: InterceptResult,
) -> bool:
    context = _runtime._CONTEXT.get()
    if context is None or context.unlimited_fuel:
        return False

    # Tow already has an earlier, stronger movement-phase result. Preserve it.
    if order.ship_id in context.tow_outcomes:
        return False

    # Invalid target locks fail without Intercept movement and therefore do not
    # depend on the phase-aligned fuel state.
    if result.status == InterceptStatus.FAILED_INVALID_TARGET:
        return False

    # Existing unresolved geometry/ordering remains unresolved for its original
    # reason; do not replace a more specific boundary with the fuel boundary.
    if result.position is None or not result.certain:
        return False

    # With no available geometric movement distance, the ship cannot move in
    # Intercept regardless of fuel. A positive-speed valid Intercept is withheld
    # even when the geometry happens to place the target at the origin, because
    # the target may itself have an unresolved earlier/Intercept position.
    if order.max_distance <= 0.0:
        return False

    return True


def _fail_closed_finite_intercept(
    result: InterceptResult,
) -> InterceptResult:
    return replace(
        result,
        status=InterceptStatus.UNRESOLVED_POST_MOVE,
        position=None,
        requested_distance=None,
        moved_distance=None,
        certain=False,
        reason=_FINITE_INTERCEPT_REASON,
        pre_final_position=None,
    )


def _resolve_intercepts(
    orders: list[InterceptOrder],
    *,
    prior_final_positions: Mapping[int, Point],
    mode: InterceptMode,
) -> dict[int, InterceptResult]:
    state = _TURN_STATE.get()
    if state is None:
        state = MovementTurnState()

    _sync_prior_state(state, prior_final_positions=prior_final_positions)

    # The state ledger is the authoritative collection of endpoints known from
    # earlier movement phases. The previous runtime facade still adds its Tow
    # positions as a compatibility guard, so passing them here is idempotent.
    results = _PREVIOUS_RESOLVE_INTERCEPTS(
        orders,
        prior_final_positions=state.known_positions(),
        mode=mode,
    )

    order_by_ship_id = {int(order.ship_id): order for order in orders}
    final_results: dict[int, InterceptResult] = {}
    for ship_id, result in results.items():
        order = order_by_ship_id.get(int(ship_id))
        resolved = result
        if order is not None and _finite_intercept_needs_fail_closed(order, result):
            resolved = _fail_closed_finite_intercept(result)

        final_results[int(ship_id)] = resolved
        if resolved.certain and resolved.position is not None:
            state.set_known(
                int(ship_id),
                resolved.position,
                phase=MovementPhase.INTERCEPT,
                reason=resolved.reason,
            )
        else:
            state.set_unresolved(
                int(ship_id),
                phase=MovementPhase.INTERCEPT,
                reason=resolved.reason,
            )

    return final_results


def _serialize_intercept(*args: Any, **kwargs: Any) -> dict[str, Any]:
    result = _PREVIOUS_SERIALIZE_INTERCEPT(*args, **kwargs)
    intercept_result = kwargs.get("result")
    if not isinstance(intercept_result, InterceptResult):
        return result
    if intercept_result.reason != _FINITE_INTERCEPT_REASON:
        return result

    warnings = list(result.get("warnings") or [])
    warning = (
        "Finite-fuel Intercept formula is supported, but the endpoint is "
        "intentionally hidden until phase-aligned Intercept fuel is available."
    )
    if warning not in warnings:
        warnings.append(warning)

    # Do not leave a geometry-only line in the API after certainty was removed.
    # Factual start/target fields remain available; only derived movement output
    # that depends on unavailable Intercept-phase state is withheld.
    result.update(
        {
            "status": InterceptStatus.UNRESOLVED_POST_MOVE.value,
            "certain": False,
            "pre_well_x": None,
            "pre_well_y": None,
            "warp_well_status": None,
            "warp_well_planet_id": None,
            "warp_well_planet_name": None,
            "warp_well_pull_distance": None,
            "predicted_x": None,
            "predicted_y": None,
            "requested_distance": None,
            "moved_distance": None,
            "displacement_distance": None,
            "reason": _FINITE_INTERCEPT_REASON,
            "warnings": warnings,
            "fuel_status": "unresolved_intercept",
            "fuel_limited": None,
            "fuel_basis": "deferred_until_intercept_phase_fuel",
            "fuel_reason": _FINITE_INTERCEPT_REASON,
        }
    )
    return result


# Extend the request-local movement facade after Tow/Move Most fuel handling.
_implementation.resolve_intercepts = _resolve_intercepts
_implementation._serialize_intercept = _serialize_intercept


def get_draft_movement_prediction(
    *,
    user_id: int,
    linked_account_id: int,
    game_id: int,
    turn: int,
) -> dict[str, Any]:
    token = _TURN_STATE.set(MovementTurnState())
    try:
        result = _runtime.get_draft_movement_prediction(
            user_id=user_id,
            linked_account_id=linked_account_id,
            game_id=game_id,
            turn=turn,
        )
        items = result.get("items")
        if isinstance(items, list):
            result = dict(result)
            result["items"] = [
                annotate_prediction_blocker(item)
                if isinstance(item, Mapping)
                else item
                for item in items
            ]
        return result
    finally:
        _TURN_STATE.reset(token)


MovementPredictionAccessError = _runtime.MovementPredictionAccessError
MovementPredictionNotFound = _runtime.MovementPredictionNotFound

__all__ = [
    "MovementPredictionAccessError",
    "MovementPredictionNotFound",
    "get_draft_movement_prediction",
]
