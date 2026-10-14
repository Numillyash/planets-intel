from app.services import movement_prediction_unified_runtime as unified
from app.services import movement_prediction_runtime as runtime
from app.services.movement_intercept import (
    InterceptMode,
    InterceptOrder,
    InterceptStatus,
    Point,
)
from app.services.movement_turn_state import MovementPhase, MovementTurnState


def _context(*, unlimited_fuel: bool) -> runtime._FuelContext:
    return runtime._FuelContext(
        owner_slot_id=1,
        unlimited_fuel=unlimited_fuel,
        ships={},
        hulls=[],
        beams=[],
        torpedoes=[],
        engines=[],
    )


def _resolve(
    *,
    unlimited_fuel: bool,
    order: InterceptOrder,
    prior: dict[int, Point],
):
    context_token = runtime._CONTEXT.set(_context(unlimited_fuel=unlimited_fuel))
    state = MovementTurnState()
    state_token = unified._TURN_STATE.set(state)
    try:
        result = unified._resolve_intercepts(
            [order],
            prior_final_positions=prior,
            mode=InterceptMode.CLASSIC,
        )[order.ship_id]
        return result, state
    finally:
        unified._TURN_STATE.reset(state_token)
        runtime._CONTEXT.reset(context_token)


def test_unlimited_intercept_keeps_verified_geometry() -> None:
    result, state = _resolve(
        unlimited_fuel=True,
        order=InterceptOrder(
            ship_id=1,
            origin=Point(0.0, 0.0),
            target_ship_id=2,
            max_distance=81.0,
        ),
        prior={2: Point(60.0, 0.0)},
    )

    assert result.status == InterceptStatus.REACHED_TARGET
    assert result.certain is True
    assert result.position == Point(60.0, 0.0)
    assert state.get(1) is not None
    assert state.get(1).phase == MovementPhase.INTERCEPT
    assert state.get(1).position == Point(60.0, 0.0)


def test_finite_fuel_moving_intercept_withholds_geometry() -> None:
    result, state = _resolve(
        unlimited_fuel=False,
        order=InterceptOrder(
            ship_id=1,
            origin=Point(0.0, 0.0),
            target_ship_id=2,
            max_distance=81.0,
        ),
        prior={2: Point(60.0, 0.0)},
    )

    assert result.status == InterceptStatus.UNRESOLVED_POST_MOVE
    assert result.certain is False
    assert result.position is None
    assert result.pre_final_position is None
    assert result.requested_distance is None
    assert result.moved_distance is None
    assert "Finite-fuel Intercept endpoint is withheld" in result.reason
    assert state.get(1) is not None
    assert state.get(1).phase == MovementPhase.INTERCEPT
    assert state.get(1).position is None
    assert state.get(1).certain is False


def test_finite_fuel_invalid_intercept_remains_known_failure() -> None:
    result, _ = _resolve(
        unlimited_fuel=False,
        order=InterceptOrder(
            ship_id=1,
            origin=Point(10.0, 20.0),
            target_ship_id=None,
            max_distance=81.0,
        ),
        prior={},
    )

    assert result.status == InterceptStatus.FAILED_INVALID_TARGET
    assert result.certain is True
    assert result.position == Point(10.0, 20.0)


def test_finite_fuel_zero_speed_intercept_keeps_origin() -> None:
    result, _ = _resolve(
        unlimited_fuel=False,
        order=InterceptOrder(
            ship_id=1,
            origin=Point(10.0, 20.0),
            target_ship_id=2,
            max_distance=0.0,
        ),
        prior={2: Point(50.0, 20.0)},
    )

    assert result.status == InterceptStatus.STAYED_NO_SPEED
    assert result.certain is True
    assert result.position == Point(10.0, 20.0)


def test_turn_state_does_not_expose_unresolved_positions() -> None:
    state = MovementTurnState()
    state.set_known(
        1,
        Point(5.0, 6.0),
        phase=MovementPhase.TOW,
        reason="known",
    )
    state.set_unresolved(
        2,
        phase=MovementPhase.MOVE_MOST,
        reason="unknown",
    )

    assert state.known_positions() == {1: Point(5.0, 6.0)}
    assert state.unresolved_ship_ids() == frozenset({2})
