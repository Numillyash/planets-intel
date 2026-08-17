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
    fighter_tracks = [
        {
            "index": index,
            "status": int(side.fighter_status[index]),
            "x": int(side.fighter_x[index]),
        }
        for index in range(len(side.fighter_status))
        if side.fighter_status[index] != 0
    ]
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
        "fighter_tracks": fighter_tracks,
        # Per-slot charge is kept in the derived trace so presentation can tell
        # an actual beam discharge from a generic target hit without making any
        # additional RNG calls or changing the combat engine.
        "beam_slots": [int(value) for value in side.beam_status[:beam_count]],
        "launcher_slots": [
            int(value) for value in side.launcher_status[:launcher_count]
        ],
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


def _track_map(side: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    tracks = side.get("fighter_tracks")
    if not isinstance(tracks, list):
        return {}
    result: dict[int, Mapping[str, Any]] = {}
    for track in tracks:
        if not isinstance(track, Mapping):
            continue
        index = track.get("index")
        if isinstance(index, int) and not isinstance(index, bool):
            result[index] = track
    return result


def _beam_discharges(old: Mapping[str, Any], new: Mapping[str, Any]) -> int:
    old_slots = old.get("beam_slots")
    new_slots = new.get("beam_slots")
    if not isinstance(old_slots, list) or not isinstance(new_slots, list):
        return 0
    count = 0
    for before, after in zip(old_slots, new_slots, strict=False):
        if not isinstance(before, int) or not isinstance(after, int):
            continue
        # A fired beam is zeroed before the end-of-cycle recharge pass. In a
        # normal cycle its visible charge therefore falls sharply (often to 0
        # or 1), unlike ordinary charging which only increases it.
        if before > 40 and after + 20 < before:
            count += 1
    return count


def _lost_fighters(
    old: Mapping[str, Any],
    new: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    old_tracks = _track_map(old)
    new_tracks = _track_map(new)
    return [
        track
        for index, track in old_tracks.items()
        if index not in new_tracks
    ]


def _combat_effects(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
    *,
    finalizing: bool,
) -> list[dict[str, Any]]:
    effects: list[dict[str, Any]] = []
    old_left = previous["left"]
    old_right = previous["right"]
    left = current["left"]
    right = current["right"]

    for side_name, old_side, side, target_name, target in (
        ("left", old_left, left, "right", right),
        ("right", old_right, right, "left", left),
    ):
        old_torps = old_side.get("torpedoes")
        new_torps = side.get("torpedoes")
        if isinstance(old_torps, int) and isinstance(new_torps, int):
            launched = max(0, old_torps - new_torps)
            if launched:
                effects.append(
                    {
                        "kind": "torpedo_launch",
                        "source": side_name,
                        "target": target_name,
                        "count": launched,
                        "source_x": int(side.get("x", 0)),
                        "target_x": int(target.get("x", 0)),
                    }
                )

        old_tracks = _track_map(old_side)
        new_tracks = _track_map(side)
        launched_ids = sorted(set(new_tracks) - set(old_tracks))
        for fighter_id in launched_ids:
            track = new_tracks[fighter_id]
            effects.append(
                {
                    "kind": "fighter_launch",
                    "source": side_name,
                    "fighter_id": fighter_id,
                    "x": int(track.get("x", side.get("x", 0))),
                }
            )

        # Fighters fire whenever their outbound track enters the target's
        # 20-unit attack radius. This is a presentation event derived directly
        # from the engine state after the cycle.
        target_x = int(target.get("x", 0))
        for fighter_id, track in new_tracks.items():
            status = track.get("status")
            x = track.get("x")
            if (
                status == 1
                and isinstance(x, int)
                and abs(x - target_x) < 20
            ):
                effects.append(
                    {
                        "kind": "fighter_attack",
                        "source": side_name,
                        "target": target_name,
                        "fighter_id": fighter_id,
                        "source_x": x,
                        "target_x": target_x,
                    }
                )

    left_beams = _beam_discharges(old_left, left)
    right_beams = _beam_discharges(old_right, right)
    left_lost = [] if finalizing else _lost_fighters(old_left, left)
    right_lost = [] if finalizing else _lost_fighters(old_right, right)

    # Beam-vs-fighter happens before fighter dogfights in the Host cycle. Match
    # observed fighter removals to opposing beam discharges first; any remaining
    # removals are represented as fighter dogfight losses below.
    left_beam_fighter = min(left_beams, len(right_lost))
    right_beam_fighter = min(right_beams, len(left_lost))

    for source, target, count, lost in (
        ("left", "right", left_beam_fighter, right_lost),
        ("right", "left", right_beam_fighter, left_lost),
    ):
        for track in lost[:count]:
            effects.append(
                {
                    "kind": "beam_fighter",
                    "source": source,
                    "target": target,
                    "target_x": int(track.get("x", 0)),
                }
            )

    for source, target, count in (
        ("left", "right", max(0, left_beams - left_beam_fighter)),
        ("right", "left", max(0, right_beams - right_beam_fighter)),
    ):
        if count:
            source_side = left if source == "left" else right
            target_side = right if target == "right" else left
            effects.append(
                {
                    "kind": "beam_ship",
                    "source": source,
                    "target": target,
                    "count": count,
                    "source_x": int(source_side.get("x", 0)),
                    "target_x": int(target_side.get("x", 0)),
                }
            )

    for lost_side, lost in (
        ("left", left_lost[right_beam_fighter:]),
        ("right", right_lost[left_beam_fighter:]),
    ):
        for track in lost:
            effects.append(
                {
                    "kind": "fighter_dogfight_loss",
                    "lost_side": lost_side,
                    "x": int(track.get("x", 0)),
                }
            )

    return effects


def _frame(
    engine: NuHostClassicReplay,
    previous: dict[str, Any] | None,
    *,
    finalizing: bool = False,
) -> dict[str, Any]:
    left = _side_snapshot(engine.status[0])
    right = _side_snapshot(engine.status[1])
    current: dict[str, Any] = {
        "cycle": engine.time,
        "seed": engine.seed,
        "left": left,
        "right": right,
        "events": [],
        "effects": [],
    }
    events: list[str] = current["events"]

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
        current["effects"] = _combat_effects(
            previous,
            current,
            finalizing=finalizing,
        )

    return current


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

    final = _frame(engine, previous, finalizing=True)
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
