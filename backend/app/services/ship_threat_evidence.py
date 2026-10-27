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
