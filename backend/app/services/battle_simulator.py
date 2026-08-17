from __future__ import annotations

from copy import deepcopy
import random
from typing import Any, Mapping

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game_rule_catalog import GameRuleCatalog
from app.services.vcr_replay import ReplayUnsupported
from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog


CLASSIC_START_SEEDS = tuple(range(1, 119))


def _combatant_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    is_planet = int(raw.get("hull_id", 0)) <= 0
    return {
        "objectid": raw.get("object_id"),
        "name": raw.get("name"),
        "beamcount": int(raw.get("beam_count", 0)),
        "launchercount": int(raw.get("launcher_count", 0)),
        "baycount": int(raw.get("bay_count", 0)),
        "hullid": int(raw.get("hull_id", 0)),
        "beamid": int(raw.get("beam_id", 0)),
        "torpedoid": int(raw.get("torpedo_id", 0)),
        "shield": int(raw.get("shield", 0)),
        "damage": int(raw.get("damage", 0)),
        "crew": int(raw.get("crew", 0)),
        "mass": int(raw.get("mass", 100)),
        "raceid": raw.get("race_id"),
        "beamkillbonus": int(raw.get("beam_kill_rate", 1)),
        "beamchargerate": int(raw.get("beam_charge_rate", 1)),
        "torpchargerate": int(raw.get("torp_charge_rate", 1)),
        "torpmisspercent": int(raw.get("torp_miss_rate", 35)),
        "crewdefensepercent": int(raw.get("crew_defense_rate", 0)),
        "torpedos": int(raw.get("torpedoes", 0)),
        "fighters": int(raw.get("fighters", 0)),
        "hasstarbase": bool(is_planet and raw.get("source_kind") == "known_planet"),
    }


def _build_payload(
    *,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    seed: int,
) -> dict[str, Any]:
    return {
        "id": 0,
        "turn": 0,
        "seed": seed,
        "battletype": 1,
        "leftownerid": left.get("owner_id"),
        "rightownerid": right.get("owner_id"),
        "left": _combatant_payload(left),
        "right": _combatant_payload(right),
    }


def _right_balance_eligible(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    return (
        int(left.get("hull_id", 0)) > 0
        and int(right.get("hull_id", 0)) > 0
        and int(left.get("bay_count", 0)) > 0
        and int(right.get("mass", 0)) >= 140
    )


def _with_right_balance_bonus(
    payload: Mapping[str, Any],
    *,
    applied: bool,
) -> dict[str, Any]:
    result = deepcopy(dict(payload))
    if not applied:
        return result
    right = result.get("right")
    if not isinstance(right, dict):
        raise ReplayUnsupported("right combatant payload is missing")
    right["mass"] = int(right.get("mass", 0)) + 360
    return result


def _catalog(game_id: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]] | None:
    with SessionLocal() as session:
        catalog = session.execute(
            select(GameRuleCatalog).where(GameRuleCatalog.game_id == game_id)
        ).scalar_one_or_none()
        if catalog is None:
            return None
        return list(catalog.beams), list(catalog.torpedos), dict(catalog.settings)


def _side_summary(trials: list[dict[str, Any]], side_name: str) -> dict[str, Any]:
    sides = [
        trial[side_name]
        for trial in trials
        if isinstance(trial.get(side_name), dict)
    ]
    total = len(trials)

    def mean(key: str) -> float:
        if not sides:
            return 0.0
        return round(sum(int(side.get(key, 0)) for side in sides) / len(sides), 2)

    destroyed = sum(bool(side.get("destroyed")) for side in sides)
    captured = sum(bool(side.get("captured")) for side in sides)
    survived = sum(bool(side.get("survived")) for side in sides)
    return {
        "destroyed_count": destroyed,
        "captured_count": captured,
        "survived_count": survived,
        "destroyed_percent": round(destroyed * 100 / total, 2) if total else 0.0,
        "captured_percent": round(captured * 100 / total, 2) if total else 0.0,
        "survived_percent": round(survived * 100 / total, 2) if total else 0.0,
        "mean_final_shield": mean("shield"),
        "mean_final_damage": mean("damage"),
        "mean_final_crew": mean("crew"),
        "mean_final_torpedoes": mean("torpedoes"),
        "mean_final_fighters": mean("fighters"),
    }


def _aggregate(trials: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(trials)
    counts: dict[str, int] = {}
    for trial in trials:
        labels = trial.get("result")
        if not isinstance(labels, list) or not labels:
            key = "unknown"
        else:
            key = "+".join(str(label) for label in labels)
        counts[key] = counts.get(key, 0) + 1

    outcomes = [
        {
            "outcome": outcome,
            "count": count,
            "percent": round(count * 100 / total, 2) if total else 0.0,
        }
        for outcome, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "sample_count": total,
        "outcomes": outcomes,
        "sides": {
            "left": _side_summary(trials, "left"),
            "right": _side_summary(trials, "right"),
        },
    }


def run_battle_simulator_once(
    *,
    game_id: int,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    seed: int,
    right_balance_bonus: str,
    sampling_seed: int | None,
) -> dict[str, Any] | None:
    catalog = _catalog(game_id)
    if catalog is None:
        return None
    beams, torpedoes, settings = catalog

    eligible = _right_balance_eligible(left, right)
    rng = random.Random(sampling_seed)
    if right_balance_bonus == "on":
        bonus_applied = eligible
    elif right_balance_bonus == "off":
        bonus_applied = False
    else:
        bonus_applied = eligible and rng.random() < 0.60

    payload = _build_payload(left=left, right=right, seed=seed)
    payload = _with_right_balance_bonus(payload, applied=bonus_applied)

    try:
        result = replay_nuhost_from_nu_catalog(
            payload,
            beams=beams,
            torpedoes=torpedoes,
            settings=settings,
        )
    except ReplayUnsupported as exc:
        return {
            "game_id": game_id,
            "supported": False,
            "reason": str(exc),
            "basis": "standalone_battle_simulator",
            "persisted": False,
        }

    return {
        **result,
        "game_id": game_id,
        "supported": True,
        "reason": None,
        "basis": "standalone_battle_simulator",
        "persisted": False,
        "start_seed": seed,
        "right_balance": {
            "eligible": eligible,
            "mode": right_balance_bonus,
            "applied": bonus_applied,
            "mass_bonus": 360 if bonus_applied else 0,
        },
        "sources": {
            "left": {
                "kind": left.get("source_kind"),
                "id": left.get("source_id"),
                "notes": list(left.get("notes") or []),
            },
            "right": {
                "kind": right.get("source_kind"),
                "id": right.get("source_id"),
                "notes": list(right.get("notes") or []),
            },
        },
    }


def run_battle_simulator_odds(
    *,
    game_id: int,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    battles: int,
    sampling_seed: int | None,
) -> dict[str, Any] | None:
    catalog = _catalog(game_id)
    if catalog is None:
        return None
    beams, torpedoes, settings = catalog

    eligible = _right_balance_eligible(left, right)
    rng = random.Random(sampling_seed)

    # Cache deterministic terminal states. A Classic single engagement only
    # varies here by combat start seed and the independent HOST 360kt balance
    # branch. Large user samples therefore need at most 236 actual replays.
    cache: dict[tuple[int, bool], dict[str, Any]] = {}
    trials: list[dict[str, Any]] = []

    try:
        for _ in range(battles):
            seed = rng.choice(CLASSIC_START_SEEDS)
            bonus_applied = eligible and rng.random() < 0.60
            key = (seed, bonus_applied)
            result = cache.get(key)
            if result is None:
                payload = _build_payload(left=left, right=right, seed=seed)
                payload = _with_right_balance_bonus(payload, applied=bonus_applied)
                result = replay_nuhost_from_nu_catalog(
                    payload,
                    beams=beams,
                    torpedoes=torpedoes,
                    settings=settings,
                )
                cache[key] = result
            trials.append(result)
    except ReplayUnsupported as exc:
        return {
            "game_id": game_id,
            "supported": False,
            "reason": str(exc),
            "basis": "standalone_battle_simulator_sampling",
            "persisted": False,
            "sample_count": 0,
            "outcomes": [],
            "sides": {},
        }

    return {
        "game_id": game_id,
        "supported": True,
        "reason": None,
        "basis": "standalone_battle_simulator_sampling",
        "persisted": False,
        "sampling": {
            "requested_battles": battles,
            "sampling_seed": sampling_seed,
            "classic_start_seeds": len(CLASSIC_START_SEEDS),
            "right_balance_eligible": eligible,
            "right_balance_probability": 0.60 if eligible else 0.0,
            "unique_terminal_replays_computed": len(cache),
        },
        "sources": {
            "left": {
                "kind": left.get("source_kind"),
                "id": left.get("source_id"),
                "notes": list(left.get("notes") or []),
            },
            "right": {
                "kind": right.get("source_kind"),
                "id": right.get("source_id"),
                "notes": list(right.get("notes") or []),
            },
        },
        **_aggregate(trials),
    }
