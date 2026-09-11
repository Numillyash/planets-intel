from app.services.movement_prediction_blockers import (
    MovementPredictionBlocker,
    classify_prediction_blocker,
)


def _row(**overrides):
    row = {
        "certain": False,
        "predicted_x": None,
        "predicted_y": None,
        "status": "unresolved",
        "fuel_status": "not_evaluated",
        "fuel_basis": "not_evaluated",
        "fuel_reason": "",
        "tow_lock_status": None,
        "reason": "",
        "warnings": [],
    }
    row.update(overrides)
    return row


def test_certain_endpoint_has_no_blocker() -> None:
    blocker, reason = classify_prediction_blocker(
        _row(certain=True, predicted_x=10, predicted_y=20)
    )

    assert blocker is None
    assert reason is None


def test_finite_intercept_phase_state_is_not_labeled_unknown_rule() -> None:
    blocker, reason = classify_prediction_blocker(
        _row(fuel_basis="deferred_until_intercept_phase_fuel")
    )

    assert blocker == MovementPredictionBlocker.PHASE_STATE_REQUIRED
    assert "Host phase" in reason


def test_finite_tow_phase_state_is_not_labeled_unknown_rule() -> None:
    blocker, _ = classify_prediction_blocker(
        _row(fuel_basis="deferred_until_tow_phase_fuel_and_mass")
    )

    assert blocker == MovementPredictionBlocker.PHASE_STATE_REQUIRED


def test_true_partial_runtime_gap_is_explicit() -> None:
    blocker, reason = classify_prediction_blocker(
        _row(fuel_status="unsupported_partial_waypoint")
    )

    assert blocker == MovementPredictionBlocker.IMPLEMENTATION_GAP
    assert "planets-lab" in reason


def test_missing_mass_is_missing_fact() -> None:
    blocker, _ = classify_prediction_blocker(
        _row(
            fuel_status="unknown",
            fuel_reason="Fuel-limited endpoint cannot be resolved because factual movement mass is incomplete.",
        )
    )

    assert blocker == MovementPredictionBlocker.MISSING_FACT


def test_tow_contest_is_order_ambiguity() -> None:
    blocker, _ = classify_prediction_blocker(
        _row(tow_lock_status="ambiguous_contest")
    )

    assert blocker == MovementPredictionBlocker.ORDER_AMBIGUITY


def test_tow_chain_remains_unsupported_host_rule() -> None:
    blocker, _ = classify_prediction_blocker(
        _row(tow_lock_status="unsupported_chain")
    )

    assert blocker == MovementPredictionBlocker.UNSUPPORTED_HOST_RULE


def test_unresolved_upstream_movement_is_dependency() -> None:
    blocker, _ = classify_prediction_blocker(
        _row(reason="Target movement depends on an unresolved earlier movement endpoint.")
    )

    assert blocker == MovementPredictionBlocker.DEPENDENCY_UNRESOLVED
