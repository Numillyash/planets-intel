"""Deterministic NuHost Classic VCR replay.

The combat loop is a Python adaptation of the Host/NuHost VCR algorithm in
PCC2 Next Generation (c2ng), game/vcr/classic/hostalgorithm.{hpp,cpp}.

c2ng copyright (c) 2001-2023 Stefan Reuther & contributors.
The relevant source is distributed under the BSD 3-Clause license.
See THIRD_PARTY_NOTICES.md in this repository.

This module is a derived-intelligence component. It never mutates factual
CombatObservation payloads.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


RANDOM_SIZE = 119
MAX_BEAMS = 10
MAX_LAUNCHERS = 10
MAX_FIGHTER_TRACKS = 19

RANDOM_1_20 = (
    9, 8, 11, 8, 5, 5, 9, 10, 15, 2, 10, 4, 14, 18, 1, 14, 15, 17, 2, 4,
    10, 13, 16, 17, 11, 10, 14, 7, 2, 8, 13, 13, 18, 6, 13, 12, 6, 12, 6,
    14, 4, 1, 20, 16, 16, 2, 8, 10, 18, 4, 20, 16, 17, 15, 6, 19, 16, 14,
    2, 15, 11, 6, 9, 17, 15, 4, 3, 12, 16, 19, 12, 18, 11, 13, 13, 8, 3, 2,
    15, 5, 12, 6, 10, 6, 9, 16, 20, 19, 18, 17, 11, 1, 4, 12, 7, 13, 15, 5,
    7, 12, 3, 3, 7, 14, 10, 18, 13, 3, 16, 14, 4, 13, 9, 14, 2, 9, 7, 4, 15,
)

RANDOM_1_100 = (
    42, 36, 54, 39, 23, 21, 41, 45, 73, 5, 47, 14, 71, 89, 2, 70, 76, 83, 5,
    16, 50, 64, 78, 87, 53, 47, 66, 33, 5, 37, 63, 61, 88, 29, 62, 58, 26, 61,
    30, 67, 16, 2, 98, 78, 81, 7, 37, 46, 88, 15, 99, 77, 82, 75, 25, 96, 79,
    69, 5, 71, 54, 25, 43, 87, 75, 17, 13, 58, 78, 96, 57, 87, 52, 63, 64, 36,
    14, 5, 73, 23, 58, 29, 48, 27, 43, 77, 99, 95, 88, 84, 55, 2, 15, 57, 33,
    61, 76, 22, 31, 61, 11, 13, 31, 70, 45, 92, 61, 11, 80, 71, 14, 62, 44, 70,
    4, 40, 32, 18, 74,
)

RANDOM_1_17 = (
    8, 7, 10, 7, 5, 4, 7, 8, 13, 2, 8, 3, 12, 15, 1, 12, 13, 14, 2, 3, 9, 11,
    13, 15, 9, 8, 12, 6, 2, 7, 11, 11, 15, 5, 11, 10, 5, 11, 6, 12, 3, 1, 17,
    14, 14, 2, 7, 8, 15, 3, 17, 13, 14, 13, 5, 16, 14, 12, 2, 12, 10, 5, 8, 15,
    13, 4, 3, 10, 13, 16, 10, 15, 9, 11, 11, 7, 3, 2, 13, 5, 10, 5, 9, 5, 8,
    13, 17, 16, 15, 14, 10, 1, 3, 10, 6, 11, 13, 4, 6, 11, 3, 3, 6, 12, 8, 16,
    11, 3, 14, 12, 3, 11, 8, 12, 2, 7, 6, 4, 13,
)


class ReplayUnsupported(ValueError):
    """The factual VCR cannot be replayed exactly with the supported rules."""


@dataclass(frozen=True)
class BeamSpec:
    component_id: int
    damage: int
    kill: int


@dataclass(frozen=True)
class TorpedoSpec:
    component_id: int
    damage: int
    kill: int
    firing_range_bonus: int = 0


@dataclass
class CombatObject:
    object_id: int | None
    owner_id: int | None
    name: str | None
    beam_count: int
    launcher_count: int
    bay_count: int
    hull_id: int
    beam_id: int
    torpedo_id: int
    shield: int
    damage: int
    crew: int
    mass: int
    race_id: int | None
    beam_kill_rate: int
    beam_charge_rate: int
    torp_charge_rate: int
    torp_miss_rate: int
    crew_defense_rate: int
    torpedoes: int
    fighters: int
    is_planet: bool

    @classmethod
    def from_payload(
        cls,
        raw: Mapping[str, Any],
        *,
        owner_id: int | None,
    ) -> "CombatObject":
        hull_id = _required_int(raw, "hullid")
        return cls(
            object_id=_optional_int(raw, "objectid"),
            owner_id=owner_id,
            name=_optional_string(raw, "name"),
            beam_count=_required_int(raw, "beamcount"),
            launcher_count=_required_int(raw, "launchercount"),
            bay_count=_required_int(raw, "baycount"),
            hull_id=hull_id,
            beam_id=_required_int(raw, "beamid"),
            torpedo_id=_required_int(raw, "torpedoid"),
            shield=_required_int(raw, "shield"),
            damage=_required_int(raw, "damage"),
            crew=_required_int(raw, "crew"),
            mass=_required_int(raw, "mass"),
            race_id=_optional_int(raw, "raceid"),
            beam_kill_rate=_required_int(raw, "beamkillbonus"),
            beam_charge_rate=_required_int(raw, "beamchargerate"),
            torp_charge_rate=_required_int(raw, "torpchargerate"),
            torp_miss_rate=_required_int(raw, "torpmisspercent"),
            crew_defense_rate=_required_int(raw, "crewdefensepercent"),
            torpedoes=_required_int(raw, "torpedos"),
            fighters=_required_int(raw, "fighters"),
            is_planet=hull_id <= 0,
        )


@dataclass
class SideStatus:
    obj: CombatObject
    side: int
    beam_status: list[int] = field(default_factory=lambda: [0] * MAX_BEAMS)
    launcher_status: list[int] = field(default_factory=lambda: [0] * MAX_LAUNCHERS)
    fighter_status: list[int] = field(
        default_factory=lambda: [0] * MAX_FIGHTER_TRACKS
    )
    fighter_x: list[int] = field(default_factory=lambda: [0] * MAX_FIGHTER_TRACKS)
    object_x: int = 0
    damage_limit: int = 100
    num_fighters_out: int = 0
    torp_firing_range: int = 300
    torp_kill_power: int = 0
    torp_damage_power: int = 0
    beam_kill_power: int = 0
    beam_damage_power: int = 0


def _required_int(raw: Mapping[str, Any], key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReplayUnsupported(f"VCR field {key!r} is missing or is not an integer")
    return value


def _optional_int(raw: Mapping[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _optional_string(raw: Mapping[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _folded(record: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key).casefold(): value for key, value in record.items()}


def _catalog_int(
    record: Mapping[str, Any],
    *keys: str,
) -> int | None:
    folded = _folded(record)
    for key in keys:
        value = folded.get(key.casefold())
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def beam_specs_from_catalog(
    records: Sequence[Mapping[str, Any]],
) -> dict[int, BeamSpec]:
    result: dict[int, BeamSpec] = {}
    for record in records:
        component_id = _catalog_int(record, "id")
        damage = _catalog_int(
            record,
            "damage",
            "blast",
            "damagepower",
            "damage_power",
            "blastpower",
        )
        kill = _catalog_int(record, "kill", "killpower", "kill_power")
        if component_id is None or damage is None or kill is None:
            continue
        result[component_id] = BeamSpec(component_id, damage, kill)
    return result


def torpedo_specs_from_catalog(
    records: Sequence[Mapping[str, Any]],
) -> dict[int, TorpedoSpec]:
    result: dict[int, TorpedoSpec] = {}
    for record in records:
        component_id = _catalog_int(record, "id")
        damage = _catalog_int(
            record,
            "damage",
            "blast",
            "damagepower",
            "damage_power",
            "blastpower",
        )
        kill = _catalog_int(record, "kill", "killpower", "kill_power")
        if component_id is None or damage is None or kill is None:
            continue

        explicit_bonus = _catalog_int(
            record,
            "firingrangebonus",
            "firing_range_bonus",
            "rangebonus",
        )
        if explicit_bonus is not None:
            range_bonus = explicit_bonus
        else:
            raw_range = _catalog_int(record, "range", "firingrange")
            if raw_range is not None and raw_range >= 1000:
                range_bonus = raw_range // 100 - 300
            elif raw_range is not None and raw_range >= 300:
                range_bonus = raw_range - 300
            else:
                range_bonus = 0

        result[component_id] = TorpedoSpec(
            component_id=component_id,
            damage=damage,
            kill=kill,
            firing_range_bonus=range_bonus,
        )
    return result


def combat_rng_from_settings(settings: Mapping[str, Any]) -> int | None:
    folded = _folded(settings)
    for key in ("combatrng", "combat_rng"):
        value = folded.get(key)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            return int(value)
    return None


class NuHostClassicReplay:
    """Exact deterministic replay for the classic 119-entry NuHost RNG."""

    def __init__(
        self,
        *,
        seed: int,
        left: CombatObject,
        right: CombatObject,
        beams: Mapping[int, BeamSpec],
        torpedoes: Mapping[int, TorpedoSpec],
    ) -> None:
        if seed < 0 or seed > RANDOM_SIZE:
            raise ReplayUnsupported(
                "only the classic 119-entry NuHost combat RNG is supported"
            )
        if left.beam_count > MAX_BEAMS or right.beam_count > MAX_BEAMS:
            raise ReplayUnsupported("VCR contains more than 10 beams")
        if (
            left.launcher_count > MAX_LAUNCHERS
            or right.launcher_count > MAX_LAUNCHERS
        ):
            raise ReplayUnsupported("VCR contains more than 10 launchers")

        self.beams = dict(beams)
        self.torpedoes = dict(torpedoes)
        self.seed = seed % RANDOM_SIZE
        self.time = 0
        self.status = [
            SideStatus(deepcopy(left), side=0),
            SideStatus(deepcopy(right), side=1),
        ]
        self.result: list[str] = []

        for side in self.status:
            self._initialize_weapon_power(side)

        self.status[0].object_x = 30
        self.status[1].object_x = 570 if right.is_planet else 610

        for side in self.status:
            self._preload_weapons(side)
            side.damage_limit = 151 if side.obj.race_id == 2 else 100

        if self.status[1].obj.is_planet:
            self.status[1].damage_limit = 100

    def _initialize_weapon_power(self, side: SideStatus) -> None:
        if side.obj.beam_id > 0:
            beam = self.beams.get(side.obj.beam_id)
            if beam is None:
                raise ReplayUnsupported(
                    f"beam #{side.obj.beam_id} is absent from the game rule catalog"
                )
            side.beam_damage_power = beam.damage
            side.beam_kill_power = beam.kill

        if side.obj.torpedo_id > 0:
            torpedo = self.torpedoes.get(side.obj.torpedo_id)
            if torpedo is None:
                raise ReplayUnsupported(
                    f"torpedo #{side.obj.torpedo_id} is absent from the game rule catalog"
                )
            side.torp_firing_range = 300 + torpedo.firing_range_bonus
            side.torp_damage_power = 2 * torpedo.damage
            side.torp_kill_power = 2 * torpedo.kill
        else:
            side.torp_firing_range = 10000

    def _set_beam_type(self, side: SideStatus, beam_id: int) -> None:
        side.obj.beam_id = beam_id
        if beam_id <= 0:
            side.beam_damage_power = 0
            side.beam_kill_power = 0
            return
        beam = self.beams.get(beam_id)
        if beam is None:
            raise ReplayUnsupported(
                f"beam #{beam_id} required by planet damage emulation is absent"
            )
        side.beam_damage_power = beam.damage
        side.beam_kill_power = beam.kill

    def _random(self, table: Sequence[int]) -> int:
        self.seed = 1 if self.seed >= RANDOM_SIZE else self.seed + 1
        return table[self.seed - 1]

    def _random_1_20(self) -> int:
        return self._random(RANDOM_1_20)

    def _random_1_100(self) -> int:
        return self._random(RANDOM_1_100)

    def _random_1_17(self) -> int:
        return self._random(RANDOM_1_17)

    @staticmethod
    def _rdivadd(a: int, b: int, plus: int) -> int:
        if a < 0 or b <= 0:
            raise ReplayUnsupported("unexpected signed RDivAdd input")
        x = a // b + plus
        remainder = a % b
        if remainder * 2 + ((x & 1) | 1) > b:
            x += 1
        return x

    @staticmethod
    def _divide_and_round(a: int, b: int) -> int:
        if a < 0 or b <= 0:
            raise ReplayUnsupported("unexpected divide-and-round input")
        return (a + b // 2) // b

    @staticmethod
    def _u8(value: int) -> int:
        return value & 0xFF

    def _hit(self, side: SideStatus, damage: int, kill: int) -> None:
        obj = side.obj
        shield = -self._rdivadd(
            80 * damage,
            obj.mass + 1,
            1 - obj.shield,
        )

        if shield < 0:
            obj.shield = 0
            new_damage = self._rdivadd(
                -80 * shield,
                obj.mass + 1,
                obj.damage + 1,
            )
            obj.damage = min(new_damage, 9999)
            shield = 0

            if obj.is_planet and damage > 1:
                right = self.status[1]
                beam_limit = 10 - right.obj.damage // 10
                if beam_limit <= 0:
                    left_beam = self.status[0].obj.beam_id
                    if left_beam > 0:
                        self._set_beam_type(right, left_beam)
                elif right.obj.beam_id > beam_limit:
                    self._set_beam_type(right, beam_limit)

        if shield == 0 and not obj.is_planet:
            effective_kill = self._divide_and_round(
                (100 - obj.crew_defense_rate) * kill,
                100,
            )
            crew = -self._rdivadd(
                80 * effective_kill,
                obj.mass + 1,
                -obj.crew,
            )
            obj.crew = max(crew, 0)

        obj.shield = shield

    @staticmethod
    def _preload_weapons(side: SideStatus) -> None:
        if side.obj.shield >= 100:
            for index in range(MAX_BEAMS):
                side.launcher_status[index] = 30
                side.beam_status[index] = 100

    def _launch_fighter(self, side: SideStatus) -> None:
        for index in range(MAX_FIGHTER_TRACKS):
            if side.fighter_status[index] == 0:
                side.obj.fighters -= 1
                side.fighter_status[index] = 1
                side.fighter_x[index] = side.object_x
                side.num_fighters_out += 1
                return

    def _launch_fighters(self, side: SideStatus) -> None:
        if side.obj.bay_count <= 0:
            return
        pick = self._random_1_20()
        if (
            pick <= side.obj.bay_count
            and side.obj.fighters > 0
            and side.num_fighters_out < MAX_FIGHTER_TRACKS
        ):
            self._launch_fighter(side)

    def _fighter_shoot(
        self,
        side: SideStatus,
        opponent: SideStatus,
        index: int,
    ) -> None:
        if abs(side.fighter_x[index] - opponent.object_x) < 20:
            self._hit(opponent, 2, 2)

    @staticmethod
    def _kill_fighter(side: SideStatus, index: int) -> None:
        side.fighter_status[index] = 0
        side.num_fighters_out -= 1

    def _fighter_stuff(self) -> None:
        left, right = self.status

        for index in range(MAX_FIGHTER_TRACKS):
            if left.fighter_status[index] == 1:
                if left.fighter_x[index] > right.object_x + 10:
                    left.fighter_status[index] = 2
                    left.fighter_x[index] -= 4
                else:
                    left.fighter_x[index] += 4
                    self._fighter_shoot(left, right, index)
            elif left.fighter_status[index] == 2:
                if left.fighter_x[index] < left.object_x:
                    left.obj.fighters += 1
                    left.fighter_status[index] = 0
                    left.num_fighters_out -= 1
                else:
                    left.fighter_x[index] -= 4

            if right.fighter_status[index] == 1:
                if right.fighter_x[index] < left.object_x - 10:
                    right.fighter_status[index] = 2
                    right.fighter_x[index] += 4
                else:
                    right.fighter_x[index] -= 4
                    self._fighter_shoot(right, left, index)
            elif right.fighter_status[index] == 2:
                if right.fighter_x[index] > right.object_x:
                    right.obj.fighters += 1
                    right.fighter_status[index] = 0
                    right.num_fighters_out -= 1
                else:
                    right.fighter_x[index] += 4

        if left.num_fighters_out <= 0 or right.num_fighters_out <= 0:
            return

        for left_index in range(MAX_FIGHTER_TRACKS):
            if left.fighter_status[left_index] == 0:
                continue
            for right_index in range(MAX_FIGHTER_TRACKS):
                if right.fighter_status[right_index] == 0:
                    continue
                if left.fighter_x[left_index] != right.fighter_x[right_index]:
                    continue

                pick = self._random_1_100()
                if left.fighter_status[left_index] == 0:
                    if pick >= 50:
                        self._kill_fighter(right, right_index)
                elif pick < 50:
                    self._kill_fighter(left, left_index)
                else:
                    self._kill_fighter(right, right_index)

    def _recharge_beams(self, side: SideStatus) -> None:
        for index in range(side.obj.beam_count):
            charge = side.beam_status[index]
            if self._random_1_100() > 50 and charge < 100:
                side.beam_status[index] = self._u8(
                    charge + side.obj.beam_charge_rate
                )

    def _fire_beam(
        self,
        side: SideStatus,
        opponent: SideStatus,
        index: int,
    ) -> None:
        charge = side.beam_status[index]
        side.beam_status[index] = 0
        damage = self._rdivadd(
            charge * side.beam_damage_power,
            100,
            0,
        )
        kill = (
            self._rdivadd(
                charge * side.beam_kill_power,
                100,
                0,
            )
            * side.obj.beam_kill_rate
        )
        self._hit(opponent, damage, kill)

    def _fire_beams(self, side: SideStatus, opponent: SideStatus) -> None:
        for index in range(side.obj.beam_count):
            pick = self._random_1_20()
            if pick < 7 and side.beam_status[index] > 50:
                self._fire_beam(side, opponent, index)

    def _fire_at_fighter(
        self,
        side: SideStatus,
        opponent: SideStatus,
        beam_index: int,
    ) -> None:
        minimum_distance = 600
        fighter_id = -1
        for index in range(MAX_FIGHTER_TRACKS):
            if opponent.fighter_status[index] == 0:
                continue
            distance = abs(opponent.fighter_x[index] - side.object_x)
            if distance < minimum_distance:
                minimum_distance = distance
                fighter_id = index

        if fighter_id >= 0:
            side.beam_status[beam_index] = 0
            self._kill_fighter(opponent, fighter_id)

    def _fire_beams_at_fighter(
        self,
        side: SideStatus,
        opponent: SideStatus,
    ) -> None:
        if opponent.num_fighters_out == 0:
            self.seed += side.obj.beam_count
            if self.seed >= RANDOM_SIZE:
                self.seed -= RANDOM_SIZE
            return

        for index in range(side.obj.beam_count):
            pick = self._random_1_20()
            if side.beam_status[index] > 40 and pick < 5:
                self._fire_at_fighter(side, opponent, index)

    def _fire_torp(
        self,
        side: SideStatus,
        opponent: SideStatus,
    ) -> None:
        pick = self._random_1_100()
        if pick >= side.obj.torp_miss_rate:
            self._hit(
                opponent,
                side.torp_damage_power,
                side.torp_kill_power,
            )

    def _fire_torpedoes(
        self,
        side: SideStatus,
        opponent: SideStatus,
    ) -> None:
        for index in range(side.obj.launcher_count):
            if side.obj.torpedoes <= 0:
                continue

            pick = self._random_1_17()
            if (
                side.launcher_status[index] > 40
                or (
                    side.launcher_status[index] > 30
                    and pick < side.obj.torpedo_id
                )
            ):
                side.obj.torpedoes -= 1
                side.launcher_status[index] = 0
                self._fire_torp(side, opponent)

            side.launcher_status[index] = self._u8(
                side.launcher_status[index] + side.obj.torp_charge_rate
            )

    def _play_cycle(self) -> bool:
        left, right = self.status
        if (
            left.obj.damage >= left.damage_limit
            or right.obj.damage >= right.damage_limit
        ):
            return False
        if left.obj.crew <= 0 or right.obj.crew <= 0:
            if not right.obj.is_planet:
                return False
        if self.time >= 2000:
            return False

        self.time += 1

        distance = right.object_x - left.object_x
        if distance > 30:
            left.object_x += 1
            distance -= 1
            if not right.obj.is_planet:
                right.object_x -= 1
                distance -= 1

        if distance < 200:
            self._fire_beams(left, right)
        self._fire_beams_at_fighter(left, right)
        self._fire_beams_at_fighter(right, left)
        if distance < 200:
            self._fire_beams(right, left)

        if distance < left.torp_firing_range:
            self._fire_torpedoes(left, right)
        if distance < right.torp_firing_range:
            self._fire_torpedoes(right, left)

        self._launch_fighters(left)
        self._launch_fighters(right)
        if left.num_fighters_out > 0 or right.num_fighters_out > 0:
            self._fighter_stuff()

        self._recharge_beams(left)
        self._recharge_beams(right)
        return True

    @staticmethod
    def _return_fighters(side: SideStatus) -> None:
        for index in range(MAX_FIGHTER_TRACKS):
            if side.fighter_status[index] != 0:
                side.obj.fighters += 1
                side.fighter_status[index] = 0
                side.num_fighters_out -= 1

    def _finish_result(self) -> list[str]:
        left, right = self.status
        result: list[str] = []

        if right.obj.is_planet:
            if left.obj.damage >= 100 or left.obj.crew <= 0:
                result.append("left_destroyed")
            if right.obj.damage >= 100:
                result.append("right_destroyed")
        else:
            if left.obj.damage >= left.damage_limit:
                result.append("left_destroyed")
            elif left.obj.crew <= 0:
                if left.obj.damage < right.damage_limit:
                    result.append("left_captured")
                else:
                    result.append("left_destroyed")

            if right.obj.damage >= right.damage_limit:
                result.append("right_destroyed")
            elif right.obj.crew <= 0:
                if right.obj.damage < left.damage_limit:
                    result.append("right_captured")
                else:
                    result.append("right_destroyed")

        if not result:
            result.append("timeout")
        return result

    def run(self) -> dict[str, Any]:
        while self._play_cycle():
            pass

        for side in self.status:
            self._return_fighters(side)

        self.result = self._finish_result()
        return {
            "engine": "nuhost_classic_119",
            "basis": "deterministic_vcr_replay",
            "source": "c2ng_hostalgorithm_bsd_port",
            "cycles": self.time,
            "final_seed": self.seed,
            "result": list(self.result),
            "left": _side_result(self.status[0].obj, self.result, "left"),
            "right": _side_result(self.status[1].obj, self.result, "right"),
        }


def _side_result(
    obj: CombatObject,
    result: Sequence[str],
    side: str,
) -> dict[str, Any]:
    destroyed = f"{side}_destroyed" in result
    captured = f"{side}_captured" in result
    return {
        "object_id": obj.object_id,
        "owner_id": obj.owner_id,
        "name": obj.name,
        "is_planet": obj.is_planet,
        "shield": obj.shield,
        "damage": obj.damage,
        "crew": obj.crew,
        "torpedoes": obj.torpedoes,
        "fighters": obj.fighters,
        "destroyed": destroyed,
        "captured": captured,
        "survived": not destroyed and not captured,
    }


def replay_nuhost_classic(
    payload: Mapping[str, Any],
    *,
    beams: Sequence[Mapping[str, Any]],
    torpedoes: Sequence[Mapping[str, Any]],
    combat_rng: int = 0,
) -> dict[str, Any]:
    """Replay one raw Planets.nu VCR using NuHost Classic combat RNG.

    ``combat_rng`` must be zero. Extended RNG games are deliberately rejected
    rather than silently producing a plausible-but-wrong result.
    """
    if combat_rng != 0:
        raise ReplayUnsupported(
            f"combat RNG mode {combat_rng} is not supported; expected Classic (0)"
        )

    raw_left = payload.get("left")
    raw_right = payload.get("right")
    if not isinstance(raw_left, Mapping) or not isinstance(raw_right, Mapping):
        raise ReplayUnsupported("VCR left/right payload is missing")

    seed = _required_int(payload, "seed")
    left = CombatObject.from_payload(
        raw_left,
        owner_id=_optional_int(payload, "leftownerid"),
    )
    right = CombatObject.from_payload(
        raw_right,
        owner_id=_optional_int(payload, "rightownerid"),
    )

    beam_specs = beam_specs_from_catalog(beams)
    torpedo_specs = torpedo_specs_from_catalog(torpedoes)

    return NuHostClassicReplay(
        seed=seed,
        left=left,
        right=right,
        beams=beam_specs,
        torpedoes=torpedo_specs,
    ).run()
