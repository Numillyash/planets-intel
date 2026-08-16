from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.combat_observation import CombatObservation
from app.models.game_rule_catalog import GameRuleCatalog
from app.models.private_observation_batch import PrivateObservationBatch
from app.services.intel_access import accessible_intel_accounts
from app.services.vcr_replay import ReplayUnsupported
from app.services.vcr_replay_trace import replay_nuhost_trace


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.endswith(".png"):
            text = text[:-4]
        if text.isdigit():
            result = int(text)
            return result if result > 0 else None
    return None


def _hull_artwork_map(hulls: list[Mapping[str, Any]]) -> dict[int, int]:
    result: dict[int, int] = {}
    for hull in hulls:
        hull_id = _positive_int(hull.get("id"))
        if hull_id is None:
            continue

        image_id = None
        for key in ("img", "imageid", "image_id", "image"):
            image_id = _positive_int(hull.get(key))
            if image_id is not None:
                break

        result[hull_id] = image_id or hull_id
    return result


def _attach_artwork_ids(
    trace: dict[str, Any],
    hulls: list[Mapping[str, Any]],
) -> None:
    artwork = _hull_artwork_map(hulls)
    frames = trace.get("frames")
    if not isinstance(frames, list):
        return

    for frame in frames:
        if not isinstance(frame, dict):
            continue
        for side_name in ("left", "right"):
            side = frame.get(side_name)
            if not isinstance(side, dict):
                continue
            hull_id = _positive_int(side.get("hull_id"))
            side["image_id"] = (
                artwork.get(hull_id, hull_id)
                if hull_id is not None
                else None
            )


def _load_replay_context(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    vcr_id: int,
) -> tuple[
    dict[str, Any],
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
    dict[str, Any],
    list[Mapping[str, Any]],
] | None:
    accessible_ids = {
        account.id
        for account in accessible_intel_accounts(user_id=user_id)
    }
    if linked_account_id not in accessible_ids:
        return None

    with SessionLocal() as session:
        catalog = session.execute(
            select(GameRuleCatalog).where(
                GameRuleCatalog.game_id == game_id
            )
        ).scalar_one_or_none()
        if catalog is None:
            return None

        row = session.execute(
            select(CombatObservation, PrivateObservationBatch)
            .join(
                PrivateObservationBatch,
                PrivateObservationBatch.id == CombatObservation.batch_id,
            )
            .where(
                PrivateObservationBatch.game_id == game_id,
                PrivateObservationBatch.observer_planets_account_id.in_(
                    accessible_ids
                ),
                CombatObservation.battle_turn == turn,
                CombatObservation.vcr_id == vcr_id,
            )
            .order_by(
                PrivateObservationBatch.observed_at.desc(),
                PrivateObservationBatch.id.desc(),
            )
            .limit(1)
        ).first()

        if row is None:
            return None

        combat, _batch = row
        payload = (
            dict(combat.payload)
            if isinstance(combat.payload, dict)
            else {}
        )
        return (
            payload,
            list(catalog.beams),
            list(catalog.torpedos),
            dict(catalog.settings),
            list(catalog.hulls),
        )


def _combat_ammo_snapshot(payload: Mapping[str, Any]) -> dict[str, dict[str, int | None]]:
    result: dict[str, dict[str, int | None]] = {}
    for side_name in ("left", "right"):
        raw = payload.get(side_name)
        if not isinstance(raw, Mapping):
            result[side_name] = {"fighters": None, "torpedoes": None}
            continue
        fighters = raw.get("fighters")
        torpedoes = raw.get("torpedos")
        result[side_name] = {
            "fighters": (
                fighters
                if isinstance(fighters, int) and not isinstance(fighters, bool)
                else None
            ),
            "torpedoes": (
                torpedoes
                if isinstance(torpedoes, int) and not isinstance(torpedoes, bool)
                else None
            ),
        }
    return result


def apply_combat_scenario_overrides(
    payload: Mapping[str, Any],
    *,
    left: Mapping[str, int | None],
    right: Mapping[str, int | None],
) -> tuple[dict[str, Any], dict[str, dict[str, int]]]:
    """Clone one factual VCR and apply simulation-only ammunition assumptions."""
    scenario = deepcopy(dict(payload))
    applied: dict[str, dict[str, int]] = {"left": {}, "right": {}}

    for side_name, overrides in (("left", left), ("right", right)):
        raw_side = scenario.get(side_name)
        if not isinstance(raw_side, dict):
            raise ReplayUnsupported(f"VCR {side_name} payload is missing")

        fighters = overrides.get("fighters")
        if fighters is not None:
            raw_side["fighters"] = fighters
            applied[side_name]["fighters"] = fighters

        torpedoes = overrides.get("torpedoes")
        if torpedoes is not None:
            raw_side["torpedos"] = torpedoes
            applied[side_name]["torpedoes"] = torpedoes

    return scenario, applied


def _run_trace(
    *,
    payload: Mapping[str, Any],
    beams: list[Mapping[str, Any]],
    torpedoes: list[Mapping[str, Any]],
    settings: Mapping[str, Any],
    hulls: list[Mapping[str, Any]],
) -> dict[str, Any]:
    trace = replay_nuhost_trace(
        payload,
        beams=beams,
        torpedoes=torpedoes,
        settings=settings,
    )
    _attach_artwork_ids(trace, hulls)
    return trace


def get_combat_replay_trace(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    vcr_id: int,
) -> dict[str, Any] | None:
    context = _load_replay_context(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        vcr_id=vcr_id,
    )
    if context is None:
        return None

    payload, beams, torpedoes, settings, hulls = context
    try:
        trace = _run_trace(
            payload=payload,
            beams=beams,
            torpedoes=torpedoes,
            settings=settings,
            hulls=hulls,
        )
    except ReplayUnsupported as exc:
        return {
            "game_id": game_id,
            "turn": turn,
            "vcr_id": vcr_id,
            "supported": False,
            "reason": str(exc),
            "frames": [],
        }

    return {
        **trace,
        "game_id": game_id,
        "turn": turn,
        "vcr_id": vcr_id,
        "supported": True,
        "reason": None,
    }


def get_combat_replay_scenario(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    vcr_id: int,
    left_overrides: Mapping[str, int | None],
    right_overrides: Mapping[str, int | None],
) -> dict[str, Any] | None:
    context = _load_replay_context(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        vcr_id=vcr_id,
    )
    if context is None:
        return None

    payload, beams, torpedoes, settings, hulls = context
    baseline = _combat_ammo_snapshot(payload)

    try:
        scenario_payload, applied = apply_combat_scenario_overrides(
            payload,
            left=left_overrides,
            right=right_overrides,
        )
        trace = _run_trace(
            payload=scenario_payload,
            beams=beams,
            torpedoes=torpedoes,
            settings=settings,
            hulls=hulls,
        )
    except ReplayUnsupported as exc:
        return {
            "game_id": game_id,
            "turn": turn,
            "vcr_id": vcr_id,
            "supported": False,
            "reason": str(exc),
            "basis": "battle_planner_scenario",
            "source_basis": "factual_vcr",
            "persisted": False,
            "baseline": baseline,
            "assumptions": {"left": {}, "right": {}},
            "frames": [],
        }

    return {
        **trace,
        "game_id": game_id,
        "turn": turn,
        "vcr_id": vcr_id,
        "supported": True,
        "reason": None,
        "basis": "battle_planner_scenario",
        "source_basis": "factual_vcr",
        "engine_basis": trace.get("basis"),
        "persisted": False,
        "baseline": baseline,
        "assumptions": applied,
    }
