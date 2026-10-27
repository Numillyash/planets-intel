"""Read-only Planets.nu game-ship evidence: hull, ammo and mass."""
from typing import Any

def nonnegative_int(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None

def compatible_vcr_side(side: dict[str, Any], *, hull_id: int | None,
                        beam_slots: int | None, tube_slots: int | None,
                        fighter_bays: int | None) -> bool:
    """VCR game-ship IDs are insufficient without validating hull hardware."""
    observed_hull = nonnegative_int(side.get("hullid"))
    if hull_id is not None and observed_hull not in (None, 0, hull_id):
        return False
    beams = nonnegative_int(side.get("beamcount"))
    tubes = nonnegative_int(side.get("launchercount"))
    if beam_slots is not None and beams is not None and beams > beam_slots:
        return False
    if tube_slots is not None and tubes is not None and tubes > tube_slots:
        return False
    if tube_slots == 0 and ((nonnegative_int(side.get("torpedoid")) or 0) > 0
                            or (nonnegative_int(side.get("torpedos")) or 0) > 0):
        return False
    if fighter_bays == 0 and (nonnegative_int(side.get("fighters")) or 0) > 0:
        return False
    return True

def defender_ammo(payload: dict[str, Any], *, fighter_bays: int | None,
                  tube_slots: int | None) -> dict[str, int | str | None]:
    """Interpret generic in-game ammo using unambiguous hull weapon types."""
    ammo = nonnegative_int(payload.get("ammo"))
    fighters = nonnegative_int(payload.get("fighters"))
    torpedoes = nonnegative_int(payload.get("torpedoes"))
    if torpedoes is None:
        torpedoes = nonnegative_int(payload.get("torps"))
    fighter_basis = "explicit" if fighters is not None else None
    torpedo_basis = "explicit" if torpedoes is not None else None
    if fighters is None and (fighter_bays or 0) > 0 and tube_slots == 0:
        fighters = ammo
        if ammo is not None:
            fighter_basis = "generic_ammo_carrier"
    if torpedoes is None and (tube_slots or 0) > 0 and fighter_bays == 0:
        torpedoes = ammo
        if ammo is not None:
            torpedo_basis = "generic_ammo_torpedo"
    return {"fighters": fighters, "torpedoes": torpedoes,
            "fighter_basis": fighter_basis, "torpedo_basis": torpedo_basis}

def full_tank_scenario(*, mass: int | None, bare_mass: int | None,
                       fuel_capacity: int | None, fighter_bays: int | None
                       ) -> dict[str, int | bool | None] | None:
    """Hypothetical leftover mass; never report it as measured fighter stock."""
    if any(v is None or v <= 0 for v in (mass, bare_mass, fuel_capacity)):
        return None
    residual = mass - bare_mass - fuel_capacity
    return {
        "assumed_fuel": fuel_capacity,
        "feasible": residual >= 0,
        "remaining_mass_ceiling": residual if residual >= 0 else None,
        "fighter_ceiling": residual if residual >= 0 and (fighter_bays or 0) > 0 else None,
    }


def hull_fuel_capacity(hull: dict[str, Any] | None) -> int | None:
    """Resolve the same per-hull fuel aliases used by loadout inference.

    Planets.nu rule catalogs may spell capacity as fuel, fueltank or
    fuelcapacity. No hull-specific numeric fallback or invented data.
    """
    if not isinstance(hull, dict):
        return None
    keys = {str(key).casefold(): value for key, value in hull.items()}
    for name in ("fuel", "fueltank", "fuelcapacity"):
        value = nonnegative_int(keys.get(name))
        if value is not None:
            return value
    return None


def uniform_beam_fighter_scenarios(
    *, mass: int | None, bare_mass: int | None,
    fuel_capacity: int | None, beam_slots: int | None,
    fighter_bays: int | None, beams: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """What-if full fuel + all beam slots filled with one weapon type.

    The calculation deliberately leaves zero OTHER cargo and counts a fighter
    as 1 kt. Beam count, fuel fill, uniform weapon type and fighter count are
    NOT factual observations. Incompatible candidates are kept and marked.
    The engine is already included in the hull mass.
    """
    budget = full_tank_scenario(
        mass=mass, bare_mass=bare_mass,
        fuel_capacity=fuel_capacity, fighter_bays=fighter_bays,
    )
    if (budget is None or not budget["feasible"]
            or beam_slots is None or beam_slots <= 0
            or fighter_bays is None or fighter_bays <= 0):
        return []
    residual = budget["remaining_mass_ceiling"]
    if type(residual) is not int:
        return []
    variants: list[dict[str, Any]] = []
    for record in beams:
        if not isinstance(record, dict):
            continue
        beam_id = nonnegative_int(record.get("id"))
        beam_mass = nonnegative_int(record.get("mass"))
        if beam_id is None or beam_id <= 0 or beam_mass is None or beam_mass <= 0:
            continue
        total = beam_slots * beam_mass
        remainder = residual - total
        variants.append({
            "beam_id": beam_id,
            "beam_name": record.get("name") if isinstance(record.get("name"), str)
                         else f"Beam #{beam_id}",
            "beam_tech": nonnegative_int(record.get("techlevel")),
            "beam_count_assumed": beam_slots,
            "beam_mass_each": beam_mass,
            "beam_mass_total": total,
            "full_tank_compatible": remainder >= 0,
            "fighter_ceiling": remainder if remainder >= 0 else None,
        })
    variants.sort(key=lambda v: (v["beam_mass_total"], v["beam_id"]))
    return variants
