from __future__ import annotations

from copy import deepcopy
import random
from typing import Any, Mapping, Sequence

from app.services.combat_replay_trace import (
    CLASSIC_START_SEEDS,
    _combat_ammo_snapshot,
    _load_replay_context,
    _summarize_seed_results,
    apply_combat_scenario_overrides,
)
from app.services.vcr_replay import ReplayUnsupported
from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog


def sample_battle_results(
    seed_results: Sequence[dict[str, Any]],
    *,
    battles: int,
    sampling_seed: int | None,
) -> list[dict[str, Any]]:
    if not seed_results:
        raise ValueError("seed_results must not be empty")
    if battles <= 0:
        raise ValueError("battles must be positive")
    rng = random.Random(sampling_seed)
    return [rng.choice(seed_results) for _ in range(battles)]


def get_combat_replay_repeat_odds(
    *,
    user_id: int,
    game_id: int,
    linked_account_id: int,
    turn: int,
    vcr_id: int,
    left_overrides: Mapping[str, int | None],
    right_overrides: Mapping[str, int | None],
    battles: int,
    sampling_seed: int | None = None,
) -> dict[str, Any] | None:
    """Run a repeated-battle sample for one VCR-derived setup.

    Classic combat has a finite documented start-seed space. We evaluate each
    unique start seed once, then sample those terminal results with replacement.
    This matches the user-facing repeated-simulation workflow without wasting CPU
    replaying identical deterministic seeds thousands of times.
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
        seed_results: list[dict[str, Any]] = []
        for start_seed in CLASSIC_START_SEEDS:
            trial_payload = deepcopy(scenario_payload)
            trial_payload["seed"] = start_seed
            result = replay_nuhost_from_nu_catalog(
                trial_payload,
                beams=beams,
                torpedoes=torpedoes,
                settings=settings,
            )
            result["start_seed"] = start_seed
            seed_results.append(result)
    except ReplayUnsupported as exc:
        return {
            "game_id": game_id,
            "turn": turn,
            "vcr_id": vcr_id,
            "supported": False,
            "reason": str(exc),
            "basis": "battle_planner_repeat_sampling",
            "source_basis": "factual_vcr",
            "persisted": False,
            "baseline": baseline,
            "assumptions": {"left": {}, "right": {}},
            "sample_count": 0,
            "outcomes": [],
            "sides": {},
        }

    trials = sample_battle_results(
        seed_results,
        battles=battles,
        sampling_seed=sampling_seed,
    )
    summary = _summarize_seed_results(trials)
    summary["sampling"] = {
        "mode": "random_start_seed_with_replacement",
        "requested_battles": battles,
        "sampling_seed": sampling_seed,
        "unique_start_seed_count": len(CLASSIC_START_SEEDS),
    }

    return {
        "game_id": game_id,
        "turn": turn,
        "vcr_id": vcr_id,
        "supported": True,
        "reason": None,
        "basis": "battle_planner_repeat_sampling",
        "source_basis": "factual_vcr",
        "engine_basis": "nuhost_classic_119",
        "persisted": False,
        "baseline": baseline,
        "assumptions": applied,
        **summary,
    }
