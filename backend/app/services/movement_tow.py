from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from math import hypot
from typing import Any, Mapping, Sequence


TOW_MISSION_ID = 6


class TowLockStatus(str, Enum):
    LOCKED = "locked"
    INVALID_TARGET = "invalid_target"
    INSUFFICIENT_ENGINES = "insufficient_engines"
    NO_FUEL = "no_fuel"
    TARGET_NOT_COLOCATED = "target_not_colocated"
    TARGET_BROKE_LOCK = "target_broke_lock"
    AMBIGUOUS_CONTEST = "ambiguous_contest"
    UNSUPPORTED_CHAIN = "unsupported_chain"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class TowShipState:
    ship_id: int
    x: int | None
    y: int | None
    warp: int | None
    waypoint_x: int | None
    waypoint_y: int | None
    fuel: int | None
    engine_count: int | None
    speed_multiplier: float | None = 1.0


@dataclass(frozen=True, slots=True)
class TowAttempt:
    tower_ship_id: int
    target_ship_id: int | None


@dataclass(frozen=True, slots=True)
class TowAttemptResult:
    tower_ship_id: int
    target_ship_id: int | None
    status: TowLockStatus
    certain: bool
    reason: str

    @property
    def locked(self) -> bool:
        return self.status == TowLockStatus.LOCKED


@dataclass(frozen=True, slots=True)
class TowResolution:
    attempts: tuple[TowAttemptResult, ...]

    @property
    def successful(self) -> tuple[TowAttemptResult, ...]:
        return tuple(item for item in self.attempts if item.locked)

    @property
    def status_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(item.status.value for item in self.attempts).items()))


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return None


def payload_integer(payload: Mapping[str, Any] | None, *keys: str) -> int | None:
    if not isinstance(payload, Mapping):
        return None
    wanted = {key.casefold() for key in keys}
    for key, value in payload.items():
        if str(key).casefold() in wanted:
            return _integer(value)
    return None


def payload_tow_target_id(payload: Mapping[str, Any] | None) -> int | None:
    value = payload_integer(
        payload,
        "mission1target",
        "mission1_target_id",
        "mission1targetid",
    )
    return value if value is not None and value > 0 else None


def payload_is_tow_mission(payload: Mapping[str, Any] | None) -> bool:
    return payload_integer(payload, "mission") == TOW_MISSION_ID


def hull_engine_count(
    *,
    hull_id: int | None,
    hulls: Sequence[Mapping[str, Any]],
) -> int | None:
    if hull_id is None or hull_id <= 0:
        return None
    for hull in hulls:
        if payload_integer(hull, "id") != hull_id:
            continue
        value = payload_integer(
            hull,
            "engines",
            "enginecount",
            "engine_count",
            "engineslots",
        )
        return value if value is not None and value >= 0 else None
    return None


def _target_breaks_tow(
    target: TowShipState,
    tower: TowShipState,
) -> tuple[bool | None, str | None]:
    """Evaluate the documented/classic four-fingers tow-break predicate.

    `None` means factual inputs are insufficient to decide safely. The caller
    must keep that attempt unresolved rather than interpreting an unknown field
    as zero.
    """

    if target.fuel is None:
        return None, "target fuel is unknown"
    if target.fuel <= 25:
        return False, None

    if target.engine_count is None:
        return None, "target engine count is unknown"
    if target.engine_count < 2:
        return False, None

    if target.x is None or target.y is None:
        return None, "target position is unknown"
    if target.warp is None:
        return None, "target warp is unknown"
    if target.waypoint_x is None or target.waypoint_y is None:
        return None, "target waypoint is unknown"

    target_waypoint_distance = hypot(
        target.waypoint_x - target.x,
        target.waypoint_y - target.y,
    )
    if target_waypoint_distance <= target.warp * target.warp:
        return False, None

    if tower.warp is None:
        return None, "tower warp is unknown"
    if target.speed_multiplier is None:
        return None, "target speed multiplier is unknown"
    if tower.speed_multiplier is None:
        return None, "tower speed multiplier is unknown"

    target_speed = target.warp * target.warp * target.speed_multiplier
    tower_speed = tower.warp * tower.warp * tower.speed_multiplier
    return target_speed >= tower_speed, None


def _tow_chain_nodes(attempts: Sequence[TowAttempt]) -> frozenset[int]:
    """Return only ship ids in connected Tow components containing a chain.

    A chain exists when a Tow target is itself a Tow tower. The strict runtime
    does not resolve ordering inside that connected component, but an unrelated
    Tow pair elsewhere in the same turn must remain independently decidable.
    """

    tower_ids = {item.tower_ship_id for item in attempts}
    adjacency: dict[int, set[int]] = defaultdict(set)
    seeds: set[int] = set()

    for item in attempts:
        target_id = item.target_ship_id
        if target_id is None or target_id <= 0:
            continue
        adjacency[item.tower_ship_id].add(target_id)
        adjacency[target_id].add(item.tower_ship_id)
        if target_id in tower_ids:
            seeds.add(item.tower_ship_id)
            seeds.add(target_id)

    if not seeds:
        return frozenset()

    affected: set[int] = set()
    pending = list(seeds)
    while pending:
        ship_id = pending.pop()
        if ship_id in affected:
            continue
        affected.add(ship_id)
        pending.extend(adjacency.get(ship_id, ()))
    return frozenset(affected)


def resolve_strict_tow_locks(
    *,
    ships: Mapping[int, TowShipState],
    attempts: Sequence[TowAttempt],
    unlimited_fuel: bool = False,
) -> TowResolution:
    """Resolve the narrow deterministic Tow-lock subset used by prediction.

    This is deliberately stricter than the research simulator. Tow chains and
    same-target contests fail closed instead of selecting a winner. Chain
    failure is scoped to the connected Tow component so unrelated Tow pairs in
    the same turn remain independently resolvable.

    The historical corpus verifies route-equivalent Tow movement, but does not
    justify inventing a winning tower identity when several visible towers
    imply the same route.

    In unlimited-fuel games the tower's movement-fuel prerequisite is bypassed.
    The target's >25 KT four-fingers fuel predicate is still factual state; if
    it is unavailable the break check remains unresolved.
    """

    ordered = tuple(sorted(attempts, key=lambda item: item.tower_ship_id))
    chain_nodes = _tow_chain_nodes(ordered)

    by_target: dict[int, list[TowAttempt]] = defaultdict(list)
    for item in ordered:
        if item.target_ship_id is not None and item.target_ship_id > 0:
            by_target[item.target_ship_id].append(item)
    contested_targets = {
        target_id for target_id, targeters in by_target.items() if len(targeters) > 1
    }

    results: list[TowAttemptResult] = []
    for item in ordered:
        tower_id = item.tower_ship_id
        target_id = item.target_ship_id
        tower = ships.get(tower_id)

        if (
            tower_id in chain_nodes
            or (target_id is not None and target_id in chain_nodes)
        ):
            results.append(
                TowAttemptResult(
                    tower_id,
                    target_id,
                    TowLockStatus.UNSUPPORTED_CHAIN,
                    False,
                    "Tow chain/cycle component is not resolved by the strict prediction subset.",
                )
            )
            continue

        if (
            tower is None
            or target_id is None
            or target_id <= 0
            or target_id == tower_id
            or target_id not in ships
        ):
            results.append(
                TowAttemptResult(
                    tower_id,
                    target_id,
                    TowLockStatus.INVALID_TARGET,
                    True,
                    "Tow target is absent, invalid, or references the towing ship itself.",
                )
            )
            continue

        if target_id in contested_targets:
            results.append(
                TowAttemptResult(
                    tower_id,
                    target_id,
                    TowLockStatus.AMBIGUOUS_CONTEST,
                    False,
                    "Multiple Tow towers target the same ship; winner identity is not inferred.",
                )
            )
            continue

        target = ships[target_id]
        if tower.engine_count is None:
            results.append(
                TowAttemptResult(
                    tower_id,
                    target_id,
                    TowLockStatus.UNKNOWN,
                    False,
                    "Tower engine count is unknown.",
                )
            )
            continue
        if tower.engine_count < 2:
            results.append(
                TowAttemptResult(
                    tower_id,
                    target_id,
                    TowLockStatus.INSUFFICIENT_ENGINES,
                    True,
                    "Tow tower has fewer than two engines.",
                )
            )
            continue

        if not unlimited_fuel:
            if tower.fuel is None:
                results.append(
                    TowAttemptResult(
                        tower_id,
                        target_id,
                        TowLockStatus.UNKNOWN,
                        False,
                        "Tower fuel is unknown.",
                    )
                )
                continue
            if tower.fuel <= 0:
                results.append(
                    TowAttemptResult(
                        tower_id,
                        target_id,
                        TowLockStatus.NO_FUEL,
                        True,
                        "Tow tower has no movement fuel.",
                    )
                )
                continue

        if None in (tower.x, tower.y, target.x, target.y):
            results.append(
                TowAttemptResult(
                    tower_id,
                    target_id,
                    TowLockStatus.UNKNOWN,
                    False,
                    "Tower/target colocation cannot be established from factual positions.",
                )
            )
            continue
        if (tower.x, tower.y) != (target.x, target.y):
            results.append(
                TowAttemptResult(
                    tower_id,
                    target_id,
                    TowLockStatus.TARGET_NOT_COLOCATED,
                    True,
                    "Tow target is not colocated with the tower.",
                )
            )
            continue

        broke, break_reason = _target_breaks_tow(target, tower)
        if broke is None:
            results.append(
                TowAttemptResult(
                    tower_id,
                    target_id,
                    TowLockStatus.UNKNOWN,
                    False,
                    f"Tow-break predicate unresolved: {break_reason}.",
                )
            )
            continue
        if broke:
            results.append(
                TowAttemptResult(
                    tower_id,
                    target_id,
                    TowLockStatus.TARGET_BROKE_LOCK,
                    True,
                    "Target satisfies the four-fingers tow-break predicate.",
                )
            )
            continue

        results.append(
            TowAttemptResult(
                tower_id,
                target_id,
                TowLockStatus.LOCKED,
                True,
                "Unique factual Tow attempt satisfies the strict lock predicate.",
            )
        )

    return TowResolution(tuple(results))


__all__ = [
    "TOW_MISSION_ID",
    "TowAttempt",
    "TowAttemptResult",
    "TowLockStatus",
    "TowResolution",
    "TowShipState",
    "hull_engine_count",
    "payload_integer",
    "payload_is_tow_mission",
    "payload_tow_target_id",
    "resolve_strict_tow_locks",
]
