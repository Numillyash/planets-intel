from __future__ import annotations

from copy import deepcopy
import random
from typing import Any, Mapping, Sequence

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game_rule_catalog import GameRuleCatalog
from app.services.vcr_replay import ReplayUnsupported
from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog
from app.services.vcr_replay_trace import replay_nuhost_trace


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
        "hasstarbase": bool(is_planet and raw.get("has_starbase")),
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


def _catalog(
    game_id: int,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    list[dict[str, Any]],
] | None:
    with SessionLocal() as session:
        catalog = session.execute(
            select(GameRuleCatalog).where(GameRuleCatalog.game_id == game_id)
        ).scalar_one_or_none()
        if catalog is None:
            return None
        return (
            list(catalog.beams),
            list(catalog.torpedos),
            dict(catalog.settings),
            list(catalog.hulls),
        )


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
            parsed = int(text)
            return parsed if parsed > 0 else None
    return None


def _hull_artwork_map(hulls: Sequence[Mapping[str, Any]]) -> dict[int, int]:
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


def _attach_trace_artwork(
    trace: dict[str, Any],
    hulls: Sequence[Mapping[str, Any]],
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


def _terminal_from_trace_side(
    side: Mapping[str, Any],
    result: Sequence[str],
    side_name: str,
) -> dict[str, Any]:
    destroyed = f"{side_name}_destroyed" in result
    captured = f"{side_name}_captured" in result
    return {
        "object_id": side.get("object_id"),
        "owner_id": side.get("owner_id"),
        "name": side.get("name"),
        "is_planet": bool(side.get("is_planet")),
        "shield": int(side.get("shield", 0)),
        "damage": int(side.get("damage", 0)),
        "crew": int(side.get("crew", 0)),
        "torpedoes": int(side.get("torpedoes", 0)),
        "fighters": int(side.get("fighters", 0)),
        "destroyed": destroyed,
        "captured": captured,
        "survived": not destroyed and not captured,
    }


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
    beams, torpedoes, settings, hulls = catalog

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
        trace = replay_nuhost_trace(
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
            "frames": [],
        }

    _attach_trace_artwork(trace, hulls)
    frames = trace.get("frames")
    result_labels = trace.get("result")
    if not isinstance(frames, list) or not frames:
        raise ReplayUnsupported("visual simulator produced no frames")
    if not isinstance(result_labels, list):
        result_labels = []
    final = frames[-1]
    if not isinstance(final, dict):
        raise ReplayUnsupported("visual simulator final frame is invalid")
    final_left = final.get("left")
    final_right = final.get("right")
    if not isinstance(final_left, dict) or not isinstance(final_right, dict):
        raise ReplayUnsupported("visual simulator final combatants are invalid")

    return {
        **trace,
        "left": _terminal_from_trace_side(final_left, result_labels, "left"),
        "right": _terminal_from_trace_side(final_right, result_labels, "right"),
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
    beams, torpedoes, settings, _hulls = catalog

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


def _physical_count(raw: Mapping[str, Any], physical_key: str, effective_key: str) -> int:
    value = raw.get(physical_key)
    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, value)
    return max(0, int(raw.get(effective_key, 0)))


def _functional_weapon_limit(raw: Mapping[str, Any]) -> int:
    damage = max(0, int(raw.get("damage", 0)))
    race_id = raw.get("race_id")
    if bool(raw.get("federation_crew_bonus")):
        return 10
    if race_id == 2:
        return max(0, min(10, 15 - damage // 10))
    return max(0, min(10, 10 - damage // 10))


def _prepare_sequence_combatant(raw: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(raw))
    if int(result.get("hull_id", 0)) <= 0:
        return result

    physical_beams = _physical_count(result, "physical_beam_count", "beam_count")
    physical_launchers = _physical_count(
        result,
        "physical_launcher_count",
        "launcher_count",
    )
    physical_bays = _physical_count(result, "physical_bay_count", "bay_count")
    limit = _functional_weapon_limit(result)

    if bool(result.get("federation_crew_bonus")):
        result["beam_count"] = physical_beams
        result["launcher_count"] = physical_launchers
        result["bay_count"] = physical_bays + (3 if physical_bays > 0 else 0)
    else:
        result["beam_count"] = min(physical_beams, limit)
        result["launcher_count"] = min(physical_launchers, limit)
        result["bay_count"] = min(physical_bays, limit)
    return result


def _sequence_cache_key(raw: Mapping[str, Any]) -> tuple[Any, ...]:
    keys = (
        "hull_id",
        "race_id",
        "beam_count",
        "launcher_count",
        "bay_count",
        "beam_id",
        "torpedo_id",
        "shield",
        "damage",
        "crew",
        "mass",
        "torpedoes",
        "fighters",
        "beam_kill_rate",
        "beam_charge_rate",
        "torp_charge_rate",
        "torp_miss_rate",
        "crew_defense_rate",
        "has_starbase",
    )
    return tuple(raw.get(key) for key in keys)


def _apply_terminal_state(
    target: dict[str, Any],
    terminal: Mapping[str, Any],
) -> None:
    for key in ("shield", "damage", "crew", "torpedoes", "fighters"):
        target[key] = int(terminal.get(key, target.get(key, 0)))


def _fed_recover_shields(raw: dict[str, Any]) -> int:
    if not bool(raw.get("federation_crew_bonus")):
        return 0
    shield = max(0, min(100, int(raw.get("shield", 0))))
    loss = 100 - shield
    recovered = (loss + 2) // 4
    raw["shield"] = min(100, shield + recovered)
    return recovered


def _sequence_planet_is_unsupported(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
) -> bool:
    if len(left) == 1 and len(right) == 1:
        return False
    return any(
        int(item.get("hull_id", 0)) <= 0
        for item in [*left, *right]
    )


def _sequence_trial(
    *,
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    beams: Sequence[Mapping[str, Any]],
    torpedoes: Sequence[Mapping[str, Any]],
    settings: Mapping[str, Any],
    rng: random.Random,
    first_seed: int | None = None,
    engagement_cache: dict[tuple[Any, ...], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    left_states = [deepcopy(dict(item)) for item in left]
    right_states = [deepcopy(dict(item)) for item in right]
    left_status = ["unfought" for _ in left_states]
    right_status = ["unfought" for _ in right_states]
    engagements: list[dict[str, Any]] = []
    left_index = 0
    right_index = 0
    timed_out = False

    while left_index < len(left_states) and right_index < len(right_states):
        left_current = _prepare_sequence_combatant(left_states[left_index])
        right_current = _prepare_sequence_combatant(right_states[right_index])
        left_status[left_index] = "fighting"
        right_status[right_index] = "fighting"

        if first_seed is not None and not engagements:
            seed = first_seed
        else:
            seed = rng.choice(CLASSIC_START_SEEDS)
        eligible = _right_balance_eligible(left_current, right_current)
        bonus_applied = eligible and rng.random() < 0.60

        cache_key = (
            _sequence_cache_key(left_current),
            _sequence_cache_key(right_current),
            seed,
            bonus_applied,
        )
        result = engagement_cache.get(cache_key) if engagement_cache is not None else None
        if result is None:
            payload = _build_payload(
                left=left_current,
                right=right_current,
                seed=seed,
            )
            payload = _with_right_balance_bonus(payload, applied=bonus_applied)
            result = replay_nuhost_from_nu_catalog(
                payload,
                beams=beams,
                torpedoes=torpedoes,
                settings=settings,
            )
            if engagement_cache is not None:
                engagement_cache[cache_key] = result

        left_terminal = result.get("left")
        right_terminal = result.get("right")
        if not isinstance(left_terminal, Mapping) or not isinstance(right_terminal, Mapping):
            raise ReplayUnsupported("sequence engagement returned invalid terminal state")
        _apply_terminal_state(left_states[left_index], left_terminal)
        _apply_terminal_state(right_states[right_index], right_terminal)

        left_defeated = bool(left_terminal.get("destroyed") or left_terminal.get("captured"))
        right_defeated = bool(right_terminal.get("destroyed") or right_terminal.get("captured"))
        labels = result.get("result")
        timeout = isinstance(labels, list) and "timeout" in labels

        engagements.append(
            {
                "number": len(engagements) + 1,
                "left_index": left_index,
                "right_index": right_index,
                "start_seed": seed,
                "right_balance_applied": bonus_applied,
                "result": list(labels) if isinstance(labels, list) else [],
                "cycles": int(result.get("cycles", 0)),
                "left": dict(left_terminal),
                "right": dict(right_terminal),
            }
        )

        if timeout and not left_defeated and not right_defeated:
            left_status[left_index] = "survived"
            right_status[right_index] = "survived"
            timed_out = True
            break

        if left_defeated:
            left_status[left_index] = (
                "captured" if bool(left_terminal.get("captured")) else "destroyed"
            )
            left_index += 1
        else:
            left_status[left_index] = "survived"

        if right_defeated:
            right_status[right_index] = (
                "captured" if bool(right_terminal.get("captured")) else "destroyed"
            )
            right_index += 1
        else:
            right_status[right_index] = "survived"

        if not left_defeated and right_defeated and right_index < len(right_states):
            _fed_recover_shields(left_states[left_index])
        if not right_defeated and left_defeated and left_index < len(left_states):
            _fed_recover_shields(right_states[right_index])

        if not left_defeated and not right_defeated:
            timed_out = True
            break

    if timed_out:
        winner = "timeout"
    elif left_index >= len(left_states) and right_index >= len(right_states):
        winner = "draw"
    elif right_index >= len(right_states):
        winner = "left"
    elif left_index >= len(left_states):
        winner = "right"
    else:
        winner = "unknown"

    return {
        "winner": winner,
        "engagements": engagements,
        "left": [
            {"index": index, "status": left_status[index], **state}
            for index, state in enumerate(left_states)
        ],
        "right": [
            {"index": index, "status": right_status[index], **state}
            for index, state in enumerate(right_states)
        ],
    }


def _sequence_side_aggregate(
    trials: Sequence[Mapping[str, Any]],
    side_name: str,
    count: int,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index in range(count):
        rows: list[Mapping[str, Any]] = []
        for trial in trials:
            side = trial.get(side_name)
            if not isinstance(side, list) or index >= len(side):
                continue
            row = side[index]
            if isinstance(row, Mapping):
                rows.append(row)

        fought = [row for row in rows if row.get("status") != "unfought"]
        total = len(rows)
        status_counts: dict[str, int] = {}
        for row in rows:
            status = str(row.get("status", "unknown"))
            status_counts[status] = status_counts.get(status, 0) + 1

        def mean(key: str) -> float | None:
            if not fought:
                return None
            return round(
                sum(int(row.get(key, 0)) for row in fought) / len(fought),
                2,
            )

        source = rows[0] if rows else {}
        result.append(
            {
                "index": index,
                "name": source.get("name"),
                "source_id": source.get("source_id"),
                "fought_count": len(fought),
                "fought_percent": round(len(fought) * 100 / total, 2) if total else 0.0,
                "status_counts": status_counts,
                "mean_final_shield": mean("shield"),
                "mean_final_damage": mean("damage"),
                "mean_final_crew": mean("crew"),
                "mean_final_torpedoes": mean("torpedoes"),
                "mean_final_fighters": mean("fighters"),
            }
        )
    return result


def run_battle_simulator_sequence_once(
    *,
    game_id: int,
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    seed: int,
    sampling_seed: int | None,
) -> dict[str, Any] | None:
    catalog = _catalog(game_id)
    if catalog is None:
        return None
    beams, torpedoes, settings, _hulls = catalog
    if _sequence_planet_is_unsupported(left, right):
        return {
            "game_id": game_id,
            "supported": False,
            "reason": (
                "multi-engagement planet/starbase carry-over is not modelled yet; "
                "planet and base defense losses would otherwise be guessed"
            ),
            "basis": "standalone_battle_sequence",
            "persisted": False,
        }

    rng = random.Random(sampling_seed if sampling_seed is not None else seed)
    try:
        result = _sequence_trial(
            left=left,
            right=right,
            beams=beams,
            torpedoes=torpedoes,
            settings=settings,
            rng=rng,
            first_seed=seed,
        )
    except ReplayUnsupported as exc:
        return {
            "game_id": game_id,
            "supported": False,
            "reason": str(exc),
            "basis": "standalone_battle_sequence",
            "persisted": False,
        }

    return {
        "game_id": game_id,
        "supported": True,
        "reason": None,
        "basis": "standalone_battle_sequence",
        "persisted": False,
        "seed_policy": "requested seed for first engagement; sampled Classic seed for later engagements",
        "sequence_model": {
            "damage_ammo_crew_shields_carry": True,
            "federation_shield_recovery_between_fights": True,
            "planet_multiwave_supported": False,
        },
        **result,
    }


def run_battle_simulator_sequence_odds(
    *,
    game_id: int,
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    battles: int,
    sampling_seed: int | None,
) -> dict[str, Any] | None:
    catalog = _catalog(game_id)
    if catalog is None:
        return None
    beams, torpedoes, settings, _hulls = catalog
    if _sequence_planet_is_unsupported(left, right):
        return {
            "game_id": game_id,
            "supported": False,
            "reason": (
                "multi-engagement planet/starbase carry-over is not modelled yet; "
                "planet and base defense losses would otherwise be guessed"
            ),
            "basis": "standalone_battle_sequence_sampling",
            "persisted": False,
            "sample_count": 0,
        }

    rng = random.Random(sampling_seed)
    engagement_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
    trials: list[dict[str, Any]] = []
    try:
        for _ in range(battles):
            trials.append(
                _sequence_trial(
                    left=left,
                    right=right,
                    beams=beams,
                    torpedoes=torpedoes,
                    settings=settings,
                    rng=rng,
                    engagement_cache=engagement_cache,
                )
            )
    except ReplayUnsupported as exc:
        return {
            "game_id": game_id,
            "supported": False,
            "reason": str(exc),
            "basis": "standalone_battle_sequence_sampling",
            "persisted": False,
            "sample_count": 0,
        }

    winner_counts: dict[str, int] = {}
    engagement_counts: list[int] = []
    for trial in trials:
        winner = str(trial.get("winner", "unknown"))
        winner_counts[winner] = winner_counts.get(winner, 0) + 1
        engagements = trial.get("engagements")
        engagement_counts.append(len(engagements) if isinstance(engagements, list) else 0)

    outcomes = [
        {
            "outcome": winner,
            "count": count,
            "percent": round(count * 100 / battles, 2),
        }
        for winner, count in sorted(
            winner_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]

    return {
        "game_id": game_id,
        "supported": True,
        "reason": None,
        "basis": "standalone_battle_sequence_sampling",
        "persisted": False,
        "sample_count": battles,
        "sampling": {
            "requested_battles": battles,
            "sampling_seed": sampling_seed,
            "classic_start_seeds": len(CLASSIC_START_SEEDS),
            "right_balance_probability_when_eligible": 0.60,
            "unique_engagement_replays_computed": len(engagement_cache),
            "mean_engagements": round(sum(engagement_counts) / battles, 2),
        },
        "outcomes": outcomes,
        "sides": {
            "left": _sequence_side_aggregate(trials, "left", len(left)),
            "right": _sequence_side_aggregate(trials, "right", len(right)),
        },
        "sequence_model": {
            "damage_ammo_crew_shields_carry": True,
            "federation_shield_recovery_between_fights": True,
            "planet_multiwave_supported": False,
        },
    }
