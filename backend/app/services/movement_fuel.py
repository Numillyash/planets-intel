from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor, hypot, trunc
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class MovementMassEvidence:
    available: bool
    total_mass: int | None
    fuel_available: int | None
    engine_id: int | None
    reason: str | None
    components: dict[str, int]


@dataclass(frozen=True, slots=True)
class FuelProration:
    requested_distance: float
    fuel_available: int
    fuel_required: int
    ratio: float
    distance: float


def _integer(record: Mapping[str, Any] | None, *keys: str) -> int | None:
    if not isinstance(record, Mapping):
        return None
    normalized = {key.casefold() for key in keys}
    for key, value in record.items():
        if str(key).casefold() not in normalized:
            continue
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
    return None


def _non_negative(record: Mapping[str, Any] | None, *keys: str) -> int | None:
    value = _integer(record, *keys)
    return value if value is not None and value >= 0 else None


def _positive(record: Mapping[str, Any] | None, *keys: str) -> int | None:
    value = _integer(record, *keys)
    return value if value is not None and value > 0 else None


def _record_by_id(
    records: Sequence[Mapping[str, Any]],
    component_id: int,
) -> Mapping[str, Any] | None:
    for record in records:
        if _positive(record, "id") == component_id:
            return record
    return None


def movement_fuel_use(
    *,
    fuel_factor: int,
    total_mass: int,
    distance_traveled: int | float,
    max_distance_per_turn: int | float,
) -> int:
    """Return documented Nu normal-movement fuel use.

    Formula transferred from the verified planets-lab rule layer:

        TRUNC(FuelFactor * TRUNC(Mass/10) * TRUNC(Distance)
              / MaxDistancePerTurn / 10000)

    All inputs are non-negative, so integer floor division implements the outer
    truncation without floating-point drift.
    """

    if fuel_factor < 0:
        raise ValueError("fuel_factor must be non-negative")
    if total_mass < 0:
        raise ValueError("total_mass must be non-negative")
    if distance_traveled < 0:
        raise ValueError("distance_traveled must be non-negative")
    if max_distance_per_turn <= 0:
        raise ValueError("max_distance_per_turn must be positive")

    mass_tens = trunc(total_mass / 10)
    distance_ly = trunc(distance_traveled)
    numerator = fuel_factor * mass_tens * distance_ly
    denominator = int(max_distance_per_turn) * 10_000
    if denominator <= 0:
        raise ValueError("max_distance_per_turn must truncate to a positive integer")
    return numerator // denominator


def prorate_waypoint_distance(
    *,
    requested_distance: int | float,
    fuel_available: int,
    fuel_required: int,
) -> FuelProration:
    """Return documented insufficient-fuel waypoint-distance proration."""

    if requested_distance < 0:
        raise ValueError("requested_distance must be non-negative")
    if fuel_available < 0:
        raise ValueError("fuel_available must be non-negative")
    if fuel_required <= 0:
        raise ValueError("fuel_required must be positive")
    if fuel_available > fuel_required:
        raise ValueError("fuel_available must not exceed fuel_required")

    ratio = fuel_available / fuel_required
    return FuelProration(
        requested_distance=float(requested_distance),
        fuel_available=fuel_available,
        fuel_required=fuel_required,
        ratio=ratio,
        distance=float(requested_distance) * ratio,
    )


def _round_nearest(value: float) -> int:
    return floor(value + 0.5) if value >= 0 else ceil(value - 0.5)


def project_toward_waypoint(
    *,
    x: int,
    y: int,
    target_x: int,
    target_y: int,
    distance: int | float,
) -> tuple[int, int]:
    """Project partial Host movement with major/minor-axis integer geometry."""

    if distance < 0:
        raise ValueError("distance must be non-negative")

    dx = target_x - x
    dy = target_y - y
    waypoint_distance = hypot(dx, dy)
    if waypoint_distance == 0 or distance == 0:
        return x, y
    if distance >= waypoint_distance:
        return target_x, target_y

    abs_dx = abs(dx)
    abs_dy = abs(dy)
    if abs_dx >= abs_dy:
        major = abs_dx
        minor = abs_dy
        major_move = _round_nearest(float(distance) * major / waypoint_distance)
        minor_move = _round_nearest(major_move * minor / major) if major else 0
        move_x = major_move if dx >= 0 else -major_move
        move_y = minor_move if dy >= 0 else -minor_move
    else:
        major = abs_dy
        minor = abs_dx
        major_move = _round_nearest(float(distance) * major / waypoint_distance)
        minor_move = _round_nearest(major_move * minor / major) if major else 0
        move_y = major_move if dy >= 0 else -major_move
        move_x = minor_move if dx >= 0 else -minor_move

    return x + move_x, y + move_y


def engine_fuel_factor(
    *,
    engine_id: int | None,
    warp: int,
    engines: Sequence[Mapping[str, Any]],
) -> int | None:
    if warp < 0 or warp > 9:
        raise ValueError("warp must be between 0 and 9")
    if warp == 0:
        return 0
    if engine_id is None or engine_id <= 0:
        return None
    engine = _record_by_id(engines, engine_id)
    if engine is None:
        return None
    return _non_negative(engine, f"warp{warp}")


def movement_mass_from_private_ship(
    *,
    payload: Mapping[str, Any],
    hull_id: int | None,
    owner_observed: bool,
    hulls: Sequence[Mapping[str, Any]],
    beams: Sequence[Mapping[str, Any]],
    torpedoes: Sequence[Mapping[str, Any]],
) -> MovementMassEvidence:
    """Reconstruct factual movement mass for an owner-observed private ship.

    `ship.mass` is deliberately ignored. Missing fields never become zero.
    Actual fitted beam/tube counts are used; hull slot capacity is not a
    substitute for installed weapons.
    """

    if not owner_observed:
        return MovementMassEvidence(
            False, None, None, None,
            "movement mass requires the controlling player's private ship state",
            {},
        )
    if hull_id is None or hull_id <= 0:
        return MovementMassEvidence(False, None, None, None, "hull id is unknown", {})

    hull = _record_by_id(hulls, hull_id)
    hull_mass = _non_negative(hull, "mass")
    if hull is None or hull_mass is None:
        return MovementMassEvidence(False, None, None, None, "hull mass is absent from the rule catalog", {})

    engine_id = _positive(payload, "engineid", "engine_id")
    if engine_id is None:
        return MovementMassEvidence(False, None, None, None, "engine id is unknown", {})

    beam_count = _non_negative(payload, "beams", "beamcount", "beam_count")
    tube_count = _non_negative(
        payload,
        "tubes",
        "torpedotubes",
        "tube_count",
        "launchercount",
        "launcher_count",
    )
    if beam_count is None:
        return MovementMassEvidence(False, None, None, engine_id, "installed beam count is unknown", {})
    if tube_count is None:
        return MovementMassEvidence(False, None, None, engine_id, "installed torpedo-tube count is unknown", {})

    beam_mass_total = 0
    if beam_count > 0:
        beam_id = _positive(payload, "beamid", "beam_id")
        if beam_id is None:
            return MovementMassEvidence(False, None, None, engine_id, "beam component id is unknown", {})
        beam = _record_by_id(beams, beam_id)
        beam_mass = _non_negative(beam, "mass")
        if beam is None or beam_mass is None:
            return MovementMassEvidence(False, None, None, engine_id, "beam component mass is absent from the rule catalog", {})
        beam_mass_total = beam_mass * beam_count

    tube_mass_total = 0
    if tube_count > 0:
        torpedo_id = _positive(payload, "torpedoid", "torpedo_id")
        if torpedo_id is None:
            return MovementMassEvidence(False, None, None, engine_id, "torpedo component id is unknown", {})
        torpedo = _record_by_id(torpedoes, torpedo_id)
        tube_mass = _non_negative(torpedo, "mass")
        if torpedo is None or tube_mass is None:
            return MovementMassEvidence(False, None, None, engine_id, "torpedo-tube component mass is absent from the rule catalog", {})
        tube_mass_total = tube_mass * tube_count

    hull_bays = _non_negative(hull, "fighterbays", "bays", "baycount")
    if hull_bays is None:
        return MovementMassEvidence(False, None, None, engine_id, "hull fighter-bay count is unknown", {})

    explicit_torpedoes = _non_negative(payload, "torpedoes", "torps")
    explicit_fighters = _non_negative(payload, "fighters")
    ammo = _non_negative(payload, "ammo")

    torpedo_stock: int
    fighter_stock: int
    if tube_count > 0 and hull_bays > 0:
        if explicit_torpedoes is None or explicit_fighters is None:
            return MovementMassEvidence(
                False,
                None,
                None,
                engine_id,
                "generic ammo is ambiguous for a ship with both torpedo tubes and fighter bays",
                {},
            )
        torpedo_stock = explicit_torpedoes
        fighter_stock = explicit_fighters
    elif tube_count > 0:
        torpedo_stock = explicit_torpedoes if explicit_torpedoes is not None else (ammo if ammo is not None else -1)
        if torpedo_stock < 0:
            return MovementMassEvidence(False, None, None, engine_id, "torpedo stock is unknown", {})
        fighter_stock = explicit_fighters or 0
    elif hull_bays > 0:
        fighter_stock = explicit_fighters if explicit_fighters is not None else (ammo if ammo is not None else -1)
        if fighter_stock < 0:
            return MovementMassEvidence(False, None, None, engine_id, "fighter stock is unknown", {})
        torpedo_stock = explicit_torpedoes or 0
    else:
        torpedo_stock = explicit_torpedoes or 0
        fighter_stock = explicit_fighters or 0
        if ammo not in (None, 0) and explicit_torpedoes is None and explicit_fighters is None:
            return MovementMassEvidence(False, None, None, engine_id, "generic ammo cannot be classified for an unarmed ship", {})

    required_cargo = {
        "fuel": _non_negative(payload, "neutronium", "fuel"),
        "supplies": _non_negative(payload, "supplies"),
        "clans": _non_negative(payload, "clans", "colonists"),
        "duranium": _non_negative(payload, "duranium"),
        "tritanium": _non_negative(payload, "tritanium"),
        "molybdenum": _non_negative(payload, "molybdenum"),
    }
    missing = [key for key, value in required_cargo.items() if value is None]
    if missing:
        return MovementMassEvidence(
            False,
            None,
            required_cargo["fuel"],
            engine_id,
            "movement-mass cargo field(s) unknown: " + ", ".join(missing),
            {},
        )

    components = {
        "hull": hull_mass,
        "beams": beam_mass_total,
        "torpedo_tubes": tube_mass_total,
        "torpedoes": torpedo_stock,
        "fighters": fighter_stock,
        **{key: int(value) for key, value in required_cargo.items() if value is not None},
    }
    total_mass = sum(components.values())
    return MovementMassEvidence(
        True,
        total_mass,
        int(required_cargo["fuel"]),
        engine_id,
        None,
        components,
    )
