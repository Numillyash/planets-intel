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
from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog
from app.services.vcr_replay_trace import replay_nuhost_trace


CLASSIC_START_SEEDS = tuple(range(1, 119))


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

        # Standard Nu hull artwork commonly uses the hull id itself. Keep it as
        # a fallback, but prefer an explicit catalog image id when present.
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
        for account in accessible_intel_accounts(user_id=user_id, game_id=game_id, linked_account_id=linked_account_id)
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


def _combat_ammo_snapshot(
    payload: Mapping[str, Any],
) -> dict[str, dict[str, int | None]]:
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


def _mean(values: list[int]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _summarize_seed_results(
    trials: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(trials)
    outcome_counts: dict[str, int] = {}
    representative_seeds: dict[str, int] = {}

    for trial in trials:
        labels = trial.get("result")
        if not isinstance(labels, list):
            labels = []
        key = "+".join(str(label) for label in labels) if labels else "unknown"
        outcome_counts[key] = outcome_counts.get(key, 0) + 1
        seed = trial.get("start_seed")
        if key not in representative_seeds and isinstance(seed, int):
            representative_seeds[key] = seed

    outcomes = [
        {
            "outcome": key,
            "count": count,
            "seed_frequency_percent": round(count * 100 / total, 2) if total else 0.0,
            "representative_seed": representative_seeds.get(key),
        }
        for key, count in sorted(
            outcome_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]

    sides: dict[str, Any] = {}
    for side_name in ("left", "right"):
        side_trials = [
            trial[side_name]
            for trial in trials
            if isinstance(trial.get(side_name), dict)
        ]
        destroyed = sum(bool(side.get("destroyed")) for side in side_trials)
        captured = sum(bool(side.get("captured")) for side in side_trials)
        survived = sum(bool(side.get("survived")) for side in side_trials)
        sides[side_name] = {
            "destroyed_count": destroyed,
            "captured_count": captured,
            "survived_count": survived,
            "survival_seed_frequency_percent": (
                round(survived * 100 / total, 2) if total else 0.0
            ),
            "mean_final_shield": _mean([int(side.get("shield", 0)) for side in side_trials]),
            "mean_final_damage": _mean([int(side.get("damage", 0)) for side in side_trials]),
            "mean_final_crew": _mean([int(side.get("crew", 0)) for side in side_trials]),
            "mean_final_torpedoes": _mean([int(side.get("torpedoes", 0)) for side in side_trials]),
            "mean_final_fighters": _mean([int(side.get("fighters", 0)) for side in side_trials]),
        }

    return {
        "sample_count": total,
        "seed_space": {
            "kind": "documented_classic_start_seeds",
            "first": CLASSIC_START_SEEDS[0],
            "last": CLASSIC_START_SEEDS[-1],
            "count": len(CLASSIC_START_SEEDS),
            "assumption": "seed_frequency_is_reported_without_asserting_host_seed_uniformity",
        },
        "outcomes": outcomes,
        "sides": sides,
    }


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


def get_combat_replay_odds(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    vcr_id: int,
    left_overrides: Mapping[str, int | None],
    right_overrides: Mapping[str, int | None],
) -> dict[str, Any] | None:
    """Evaluate one VCR-derived setup across every documented Classic start seed.

    The response deliberately reports seed frequencies rather than asserting that
    Host selects these seeds uniformly. No factual or analyst-reviewed state is
    persisted.
    """
    context = _load_replay_context(
        user_id=user_id,
        game_id=game_id,
        linked_account_id=linked_account_id,
        turn=turn,
        vcr_id=vcr_id,
    )
    if context is None:
        return None

    payload, beams, torpedoes, settings, _hulls = context
    baseline = _combat_ammo_snapshot(payload)

    try:
        scenario_payload, applied = apply_combat_scenario_overrides(
            payload,
            left=left_overrides,
            right=right_overrides,
        )
        trials: list[dict[str, Any]] = []
        for seed in CLASSIC_START_SEEDS:
            trial_payload = deepcopy(scenario_payload)
            trial_payload["seed"] = seed
            result = replay_nuhost_from_nu_catalog(
                trial_payload,
                beams=beams,
                torpedoes=torpedoes,
                settings=settings,
            )
            result["start_seed"] = seed
            trials.append(result)
    except ReplayUnsupported as exc:
        return {
            "game_id": game_id,
            "turn": turn,
            "vcr_id": vcr_id,
            "supported": False,
            "reason": str(exc),
            "basis": "battle_planner_seed_sweep",
            "source_basis": "factual_vcr",
            "persisted": False,
            "baseline": baseline,
            "assumptions": {"left": {}, "right": {}},
            "sample_count": 0,
            "outcomes": [],
            "sides": {},
        }

    return {
        "game_id": game_id,
        "turn": turn,
        "vcr_id": vcr_id,
        "supported": True,
        "reason": None,
        "basis": "battle_planner_seed_sweep",
        "source_basis": "factual_vcr",
        "engine_basis": "nuhost_classic_119",
        "persisted": False,
        "baseline": baseline,
        "assumptions": applied,
        **_summarize_seed_results(trials),
    }
