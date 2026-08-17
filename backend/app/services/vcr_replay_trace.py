from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.services.vcr_replay import (
    CombatObject,
    NuHostClassicReplay,
    ReplayUnsupported,
    SideStatus,
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


def _side_snapshot(side: SideStatus) -> dict[str, Any]:
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


class TracingNuHostClassicReplay(NuHostClassicReplay):
    """Classic replay with presentation-only event recording.

    Every event is recorded at the exact engine method that performed the
    action. The overrides delegate to the base implementation and make no
    additional random-number calls, so seed progression and terminal combat
    state remain identical to ``NuHostClassicReplay``.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.cycle_effects: list[dict[str, Any]] = []
        self._fighter_kill_context: str | None = None

    def _side_name(self, side: SideStatus) -> str:
        return "left" if side is self.status[0] else "right"

    def _other_name(self, side: SideStatus) -> str:
        return "right" if side is self.status[0] else "left"

    def _play_cycle(self) -> bool:
        self.cycle_effects = []
        return super()._play_cycle()

    def _launch_fighter(self, side: SideStatus) -> None:
        before = list(side.fighter_status)
        super()._launch_fighter(side)
        for index, (old_status, new_status) in enumerate(
            zip(before, side.fighter_status, strict=True)
        ):
            if old_status == 0 and new_status != 0:
                self.cycle_effects.append(
                    {
                        "kind": "fighter_launch",
                        "source": self._side_name(side),
                        "fighter_id": index,
                        "x": int(side.fighter_x[index]),
                    }
                )
                break

    def _fighter_shoot(
        self,
        side: SideStatus,
        opponent: SideStatus,
        index: int,
    ) -> None:
        in_range = abs(side.fighter_x[index] - opponent.object_x) < 20
        if in_range:
            self.cycle_effects.append(
                {
                    "kind": "fighter_attack",
                    "source": self._side_name(side),
                    "target": self._side_name(opponent),
                    "fighter_id": index,
                    "source_x": int(side.fighter_x[index]),
                    "target_x": int(opponent.object_x),
                }
            )
        super()._fighter_shoot(side, opponent, index)

    def _fighter_stuff(self) -> None:
        previous_context = self._fighter_kill_context
        self._fighter_kill_context = "dogfight"
        try:
            super()._fighter_stuff()
        finally:
            self._fighter_kill_context = previous_context

    def _kill_fighter(self, side: SideStatus, index: int) -> None:
        if self._fighter_kill_context == "dogfight":
            self.cycle_effects.append(
                {
                    "kind": "fighter_dogfight_loss",
                    "lost_side": self._side_name(side),
                    "fighter_id": index,
                    "x": int(side.fighter_x[index]),
                }
            )
        super()._kill_fighter(side, index)

    def _fire_beam(
        self,
        side: SideStatus,
        opponent: SideStatus,
        index: int,
    ) -> None:
        self.cycle_effects.append(
            {
                "kind": "beam_ship",
                "source": self._side_name(side),
                "target": self._side_name(opponent),
                "beam_id": index,
                "source_x": int(side.object_x),
                "target_x": int(opponent.object_x),
            }
        )
        super()._fire_beam(side, opponent, index)

    def _fire_at_fighter(
        self,
        side: SideStatus,
        opponent: SideStatus,
        beam_index: int,
    ) -> None:
        minimum_distance = 600
        fighter_id = -1
        for index in range(len(opponent.fighter_status)):
            if opponent.fighter_status[index] == 0:
                continue
            distance = abs(opponent.fighter_x[index] - side.object_x)
            if distance < minimum_distance:
                minimum_distance = distance
                fighter_id = index

        target_x = (
            int(opponent.fighter_x[fighter_id])
            if fighter_id >= 0
            else None
        )
        super()._fire_at_fighter(side, opponent, beam_index)
        if fighter_id >= 0 and opponent.fighter_status[fighter_id] == 0:
            self.cycle_effects.append(
                {
                    "kind": "beam_fighter",
                    "source": self._side_name(side),
                    "target": self._side_name(opponent),
                    "beam_id": beam_index,
                    "fighter_id": fighter_id,
                    "source_x": int(side.object_x),
                    "target_x": target_x,
                }
            )

    def _fire_torp(
        self,
        side: SideStatus,
        opponent: SideStatus,
    ) -> None:
        before = (
            opponent.obj.shield,
            opponent.obj.damage,
            opponent.obj.crew,
        )
        super()._fire_torp(side, opponent)
        after = (
            opponent.obj.shield,
            opponent.obj.damage,
            opponent.obj.crew,
        )
        self.cycle_effects.append(
            {
                "kind": "torpedo_launch",
                "source": self._side_name(side),
                "target": self._side_name(opponent),
                "count": 1,
                "hit": after != before,
                "source_x": int(side.object_x),
                "target_x": int(opponent.object_x),
            }
        )


def _frame(
    engine: TracingNuHostClassicReplay,
    previous: dict[str, Any] | None,
    *,
    effects: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    left = _side_snapshot(engine.status[0])
    right = _side_snapshot(engine.status[1])
    current: dict[str, Any] = {
        "cycle": engine.time,
        "seed": engine.seed,
        "left": left,
        "right": right,
        "events": [],
        "effects": [dict(effect) for effect in (effects or [])],
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

    engine = TracingNuHostClassicReplay(
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
        current = _frame(
            engine,
            previous,
            effects=engine.cycle_effects,
        )
        frames.append(current)
        previous = current

    for side in engine.status:
        engine._return_fighters(side)

    final = _frame(engine, previous)
    if final["left"] != previous["left"] or final["right"] != previous["right"]:
        frames.append(final)

    result = engine._finish_result()

    return {
        "engine": "nuhost_classic_119",
        "basis": "deterministic_vcr_replay",
        "trace_basis": "exact_engine_event_hooks_no_extra_rng",
        "turn": payload.get("turn"),
        "vcr_id": payload.get("id"),
        "battle_type": payload.get("battletype"),
        "cycles": engine.time,
        "result": result,
        "frames": frames,
    }
