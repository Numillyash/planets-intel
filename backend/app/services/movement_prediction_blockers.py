from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping


class MovementPredictionBlocker(StrEnum):
    PHASE_STATE_REQUIRED = "phase_state_required"
    IMPLEMENTATION_GAP = "implementation_gap"
    MISSING_FACT = "missing_fact"
    DEPENDENCY_UNRESOLVED = "dependency_unresolved"
    ORDER_AMBIGUITY = "order_ambiguity"
    UNSUPPORTED_HOST_RULE = "unsupported_host_rule"


def classify_prediction_blocker(
    item: Mapping[str, Any],
) -> tuple[MovementPredictionBlocker | None, str | None]:
    """Classify why a movement row is not a trustworthy endpoint.

    This classifier is intentionally presentation/provenance logic. It must not
    turn an uncertain movement result into a certain one. The distinction lets
    the client tell apart a verified formula that lacks phase-aligned factual
    inputs from a Host rule that is still outside the reconstructed model.
    """

    if (
        bool(item.get("certain"))
        and item.get("predicted_x") is not None
        and item.get("predicted_y") is not None
    ):
        return None, None

    fuel_basis = str(item.get("fuel_basis") or "")
    fuel_status = str(item.get("fuel_status") or "")
    tow_lock_status = str(item.get("tow_lock_status") or "")
    status = str(item.get("status") or "")
    text = " ".join(
        str(value or "")
        for value in (
            item.get("reason"),
            item.get("fuel_reason"),
            " ".join(str(value) for value in (item.get("warnings") or [])),
        )
    ).casefold()

    if fuel_basis in {
        "deferred_until_tow_phase_fuel_and_mass",
        "deferred_until_intercept_phase_fuel",
        # Compatibility with rows produced before the evidence wording was
        # reconciled. Do not silently reinterpret the endpoint itself.
        "deferred_until_intercept_fuel_corpus_validation",
        "deferred_until_intercept_fuel",
    }:
        return (
            MovementPredictionBlocker.PHASE_STATE_REQUIRED,
            "The movement formula is supported, but the factual state required at this Host phase is not available.",
        )

    if tow_lock_status == "ambiguous_contest":
        return (
            MovementPredictionBlocker.ORDER_AMBIGUITY,
            "Tow lock precedence is ambiguous because multiple towers contest the same target.",
        )

    if tow_lock_status == "unsupported_chain":
        return (
            MovementPredictionBlocker.UNSUPPORTED_HOST_RULE,
            "Tow chain or cycle resolution is outside the currently reconstructed Host subset.",
        )

    if fuel_status == "unsupported_partial_waypoint":
        return (
            MovementPredictionBlocker.IMPLEMENTATION_GAP,
            "True-partial normal-movement fuel semantics are supported by planets-lab evidence, but this production path has not yet integrated them safely.",
        )

    if fuel_status in {"unsupported_zero_fuel", "unsupported_gravitonic"}:
        return (
            MovementPredictionBlocker.UNSUPPORTED_HOST_RULE,
            "This fuel-limited movement case remains outside the currently supported production Host subset.",
        )

    missing_markers = (
        "factual movement mass is incomplete",
        "engine fuel factor is unknown",
        "missing factual",
        "missing owner-visible",
        "missing ship",
        "missing target",
        "unknown engine",
        "unknown hull",
    )
    if fuel_status == "unknown" or any(marker in text for marker in missing_markers):
        return (
            MovementPredictionBlocker.MISSING_FACT,
            "A required factual input is missing or unknown; missing values are not treated as zero.",
        )

    dependency_markers = (
        "earlier movement",
        "prior movement",
        "upstream",
        "target movement",
        "post-tow",
        "post-move",
        "withheld from later movement",
        "dependency",
    )
    if any(marker in text for marker in dependency_markers):
        return (
            MovementPredictionBlocker.DEPENDENCY_UNRESOLVED,
            "This endpoint depends on another movement result that is still unresolved.",
        )

    if "ambiguous" in status.casefold() or "ambiguous" in text:
        return (
            MovementPredictionBlocker.ORDER_AMBIGUITY,
            "The applicable Host ordering or target selection is ambiguous for this row.",
        )

    return (
        MovementPredictionBlocker.UNSUPPORTED_HOST_RULE,
        "The row is uncertain because the applicable Host behavior is not supported strongly enough to emit a deterministic endpoint.",
    )


def annotate_prediction_blocker(item: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(item)
    blocker, reason = classify_prediction_blocker(result)
    result["blocker_class"] = blocker.value if blocker is not None else None
    result["blocker_reason"] = reason
    return result


__all__ = [
    "MovementPredictionBlocker",
    "annotate_prediction_blocker",
    "classify_prediction_blocker",
]
