from __future__ import annotations

from copy import deepcopy
from math import isqrt
from typing import Any, Mapping


PLANET_CARRYOVER_BASIS = "nuhost_planet_starbase_carryover_v1"


def _round_sqrt_ratio(numerator: int, denominator: int = 1) -> int:
    """Round sqrt(numerator / denominator) to nearest integer, halves up."""

    if numerator <= 0 or denominator <= 0:
        return 0
    floor_value = isqrt(numerator // denominator)
    while (floor_value + 1) * (floor_value + 1) * denominator <= numerator:
        floor_value += 1
    while floor_value * floor_value * denominator > numerator:
        floor_value -= 1
    threshold = denominator * (2 * floor_value + 1) ** 2
    return floor_value + 1 if 4 * numerator >= threshold else floor_value


def planet_fighter_count(defense: int) -> int:
    """ROUND(SQRT(MAX(0, DP - .75))) without floating point."""

    dp = max(0, int(defense))
    return _round_sqrt_ratio(max(0, 4 * dp - 3), 4)


def planet_bay_count(defense: int) -> int:
    return isqrt(max(0, int(defense)))


def planet_beam_count(
    defense: int,
    starbase_defense: int,
    starbase_mass_bonus: int,
) -> int:
    total = (
        max(0, int(defense))
        + max(0, int(starbase_defense))
        + max(0, int(starbase_mass_bonus))
    )
    return min(10, _round_sqrt_ratio(total, 3))


def planet_native_beam_tech(defense: int) -> int:
    dp = max(0, int(defense))
    if dp <= 0:
        return 0
    return max(1, min(10, isqrt(dp // 2)))


def _damage_defense_posts(defense: int, battle_damage: int) -> int:
    value = max(0, int(defense))
    damage = max(0, min(100, int(battle_damage)))
    return max(0, value - (value * damage) // 100)


def _damage_tech(tech: int, battle_damage: int) -> int:
    value = max(0, min(10, int(tech)))
    if value <= 0:
        return 0
    damage = max(0, min(100, int(battle_damage)))
    return max(1, (value * (100 - damage)) // 100)


def rebuild_planet_combatant(
    raw: Mapping[str, Any],
    *,
    shield: int | None = None,
) -> dict[str, Any]:
    """Materialize one planet/base engagement from persistent defense state."""

    result = deepcopy(dict(raw))
    planet_defense = max(0, int(result.get("planet_defense") or 0))
    has_base = bool(result.get("has_starbase"))
    base_defense = max(0, int(result.get("starbase_defense") or 0)) if has_base else 0
    base_fighters = max(0, int(result.get("starbase_fighters") or 0)) if has_base else 0
    base_tech = max(0, min(10, int(result.get("starbase_beam_tech") or 0))) if has_base else 0
    base_damage = max(0, int(result.get("starbase_damage") or 0)) if has_base else 0
    race_id = result.get("race_id")
    requested_mass_bonus = (
        max(0, min(200, int(result.get("starbase_mass_bonus") or 0)))
        if has_base
        else 0
    )
    # Robots do not receive the shielded-starbase radiation-halo mass bonus.
    base_mass_bonus = 0 if race_id == 9 else requested_mass_bonus

    can_fight = planet_defense > 0
    planet_fighters = planet_fighter_count(planet_defense) if can_fight else 0
    beams = (
        planet_beam_count(planet_defense, base_defense, base_mass_bonus)
        if can_fight
        else 0
    )
    beam_tech = (
        max(planet_native_beam_tech(planet_defense), base_tech)
        if beams > 0
        else 0
    )

    result.update(
        {
            "hull_id": 0,
            "has_starbase": has_base,
            "planet_defense": planet_defense,
            "starbase_defense": base_defense if has_base else None,
            "starbase_fighters": base_fighters if has_base else None,
            "starbase_beam_tech": base_tech if has_base else None,
            "starbase_damage": base_damage if has_base else None,
            "starbase_mass_bonus": base_mass_bonus if has_base else None,
            "beam_count": beams,
            "launcher_count": 0,
            "bay_count": (
                planet_bay_count(planet_defense) + (5 if has_base else 0)
                if can_fight
                else 0
            ),
            "beam_id": beam_tech,
            "torpedo_id": 0,
            "shield": (
                max(0, min(100, int(shield)))
                if shield is not None and can_fight
                else (100 if can_fight else 0)
            ),
            "damage": 0,
            "crew": 10_000,
            "mass": max(1, 100 + planet_defense + base_defense + base_mass_bonus),
            "torpedoes": 0,
            "fighters": planet_fighters + base_fighters if can_fight else 0,
            "physical_beam_count": None,
            "physical_launcher_count": None,
            "physical_bay_count": None,
            "federation_crew_bonus": False,
            "lizard_crew_bonus": False,
            "galactic_power": False,
        }
    )
    return result


def apply_planet_carryover(
    state: Mapping[str, Any],
    engagement_start: Mapping[str, Any],
    terminal: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the defending world for the next ship-vs-planet engagement.

    Exact Nu/Host-documented pieces:
    - planet damage resets to zero for the next engagement;
    - planet DP lose TRUNC(DP * battle_damage / 100);
    - starbase fighters are lost before generated planetary fighters;
    - every lost planetary fighter removes one additional planet DP;
    - starbase damage accumulates and a base at >=100 damage is removed;
    - starbase beam tech is reduced by newly inflicted damage;
    - defense/bay/fighter/beam/mass values are then re-derived from the
      surviving fixed-defense state.

    Planets.nu documentation states that starbase damage removes base defense
    points but does not publish the numeric loss formula. Version 1 uses the
    classic Host proportional-defense loss rule for that one transition and
    exposes ``PLANET_CARRYOVER_BASIS`` so results remain explicitly derived.
    """

    result = deepcopy(dict(state))
    battle_damage = max(0, min(100, int(terminal.get("damage", 0))))
    old_dp = max(0, int(engagement_start.get("planet_defense") or 0))
    had_base = bool(engagement_start.get("has_starbase"))
    old_base_fighters = (
        max(0, int(engagement_start.get("starbase_fighters") or 0))
        if had_base
        else 0
    )
    old_total_fighters = max(0, int(engagement_start.get("fighters", 0)))
    terminal_fighters = max(0, int(terminal.get("fighters", 0)))
    fighter_losses = max(0, old_total_fighters - terminal_fighters)

    base_fighter_losses = min(old_base_fighters, fighter_losses)
    planetary_fighter_losses = max(0, fighter_losses - base_fighter_losses)
    next_base_fighters = max(0, old_base_fighters - base_fighter_losses)

    next_dp = _damage_defense_posts(old_dp, battle_damage)
    next_dp = max(0, next_dp - planetary_fighter_losses)

    if had_base:
        old_base_damage = max(0, int(engagement_start.get("starbase_damage") or 0))
        next_base_damage = old_base_damage + battle_damage
        base_survives = next_base_damage < 100
    else:
        next_base_damage = 0
        base_survives = False

    if base_survives:
        old_base_defense = max(0, int(engagement_start.get("starbase_defense") or 0))
        old_base_tech = max(0, int(engagement_start.get("starbase_beam_tech") or 0))
        result.update(
            {
                "has_starbase": True,
                "starbase_defense": _damage_defense_posts(
                    old_base_defense,
                    battle_damage,
                ),
                "starbase_fighters": next_base_fighters,
                "starbase_beam_tech": _damage_tech(old_base_tech, battle_damage),
                "starbase_damage": next_base_damage,
                "starbase_mass_bonus": max(
                    0,
                    min(200, int(engagement_start.get("starbase_mass_bonus") or 0)),
                ),
            }
        )
    else:
        result.update(
            {
                "has_starbase": False,
                "starbase_defense": None,
                "starbase_fighters": None,
                "starbase_beam_tech": None,
                "starbase_damage": None,
                "starbase_mass_bonus": None,
            }
        )

    result["planet_defense"] = next_dp
    result = rebuild_planet_combatant(
        result,
        shield=max(0, min(100, int(terminal.get("shield", 0)))),
    )
    result.setdefault("notes", [])
    notes = list(result.get("notes") or [])
    carry_note = f"planet/base carry-over: {PLANET_CARRYOVER_BASIS}"
    if carry_note not in notes:
        notes.append(carry_note)
    result["notes"] = notes
    return result


def planet_sequence_shape_supported(
    left: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    right: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> bool:
    """Support ship queues attacking one fixed world; fail closed otherwise."""

    left_planets = [item for item in left if int(item.get("hull_id", 0)) <= 0]
    right_planets = [item for item in right if int(item.get("hull_id", 0)) <= 0]
    if not left_planets and not right_planets:
        return True
    if left_planets:
        return False
    return len(right) == 1 and len(right_planets) == 1
