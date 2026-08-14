from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.services.vcr_replay import (
    CombatObject,
    NuHostClassicReplay,
    ReplayUnsupported,
    beam_specs_from_catalog,
    combat_rng_from_settings,
    torpedo_specs_from_catalog,
)
from app.services.vcr_replay_nu import (
    normalize_nu_beams,
    normalize_nu_torpedoes,
)


def _optional_int(raw: Mapping[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _side_snapshot(side) -> dict[str, Any]:
    obj = side.obj
    beam_count = max(0, min(obj.beam_count, len(side.beam_status)))
    launcher_count = max(0, min(obj.launcher_count, len(side.launcher_status)))
    return {
        "object_id": obj.object_id,
        "owner_id": obj.owner_id,
        "name": obj.name,
        "hull_id": obj.hull_id,
        "is_planet": obj.is_planet,
        "x": side.object_x,
        "shield": obj.shield,
        "damage": obj.damage,
        "crew": obj.crew,
        "torpedoes": obj.torpedoes,
        "fighters": obj.fighters,
        "fighters_out": side.num_fighters_out,
        "beam_charge": (
            sum(side.beam_status[:beam_count]) // beam_count
            if beam_count > 0
            else None
        ),
        "launcher_charge": (
            sum(side.launcher_status[:launcher_count]) // launcher_count
            if launcher_count > 0
            else None
        ),
    }


def _frame(engine: NuHostClassicReplay, previous: dict[str, Any] | None) -> dict[str, Any]:
    left = _side_snapshot(engine.status[0])
    right = _side_snapshot(engine.status[1])
    events: list[str] = []

    if previous is not None:
        old_left = previous["left"]
        old_right = previous["right"]
        if left["torpedoes"] < old_left["torpedoes"]:
            events.append("left_torpedo")
        if right["torpedoes"] < old_right["torpedoes"]:
            events.append("right_torpedo")
        if left["fighters_out"] > old_left["fighters_out"]:
            events.append("left_fighter_launch")
        if right["fighters_out"] > old_right["fighters_out"]:
            events.append("right_fighter_launch")
        if (
            left["shield"] < old_left["shield"]
            or left["damage"] > old_left["damage"]
            or left["crew"] < old_left["crew"]
        ):
            events.append("left_hit")
        if (
            right["shield"] < old_right["shield"]
            or right["damage"] > old_right["damage"]
            or right["crew"] < old_right["crew"]
        ):
            events.append("right_hit")

    return {
        "cycle": engine.time,
        "seed": engine.seed,
        "left": left,
        "right": right,
        "events": events,
    }


def replay_nuhost_trace(
    payload: Mapping[str, Any],
    *,
    beams: Sequence[Mapping[str, Any]],
    torpedoes: Sequence[Mapping[str, Any]],
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    combat_rng = combat_rng_from_settings(settings)
    if combat_rng != 0:
        raise ReplayUnsupported(
            f"combat RNG mode {combat_rng!r} is not supported by the visual replay"
        )

    raw_left = payload.get("left")
    raw_right = payload.get("right")
    if not isinstance(raw_left, Mapping) or not isinstance(raw_right, Mapping):
        raise ReplayUnsupported("VCR left/right payload is missing")

    seed = payload.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ReplayUnsupported("VCR seed is missing")

    normalized_beams = normalize_nu_beams(beams)
    normalized_torpedoes = normalize_nu_torpedoes(torpedoes)

    engine = NuHostClassicReplay(
        seed=seed,
        left=CombatObject.from_payload(
            raw_left,
            owner_id=_optional_int(payload, "leftownerid"),
        ),
        right=CombatObject.from_payload(
            raw_right,
            owner_id=_optional_int(payload, "rightownerid"),
        ),
        beams=beam_specs_from_catalog(normalized_beams),
        torpedoes=torpedo_specs_from_catalog(normalized_torpedoes),
    )

    frames: list[dict[str, Any]] = []
    first = _frame(engine, None)
    frames.append(first)
    previous = first

    while engine._play_cycle():
        current = _frame(engine, previous)
        frames.append(current)
        previous = current

    for side in engine.status:
        engine._return_fighters(side)

    final = _frame(engine, previous)
    if final != previous:
        frames.append(final)

    result = engine._finish_result()

    return {
        "engine": "nuhost_classic_119",
        "basis": "deterministic_vcr_replay",
        "turn": payload.get("turn"),
        "vcr_id": payload.get("id"),
        "battle_type": payload.get("battletype"),
        "cycles": engine.time,
        "result": result,
        "frames": frames,
    }
