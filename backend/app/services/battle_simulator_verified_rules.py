from __future__ import annotations

from math import isqrt
from typing import Any


def federation_recover_shields(raw: dict[str, Any]) -> int:
    """Apply the corpus-verified Federation between-fight shield recovery.

    Historical Nu VCR chains discriminate this from the older
    ``25% of missing shields`` interpretation. A surviving Federation ship
    recovers up to 25 shield points before its next engagement, capped by the
    damage-reduced maximum shield level.
    """

    if not bool(raw.get("federation_crew_bonus")):
        return 0

    shield = max(0, min(100, int(raw.get("shield", 0))))
    damage = max(0, int(raw.get("damage", 0)))
    max_shield = max(0, 100 - damage)
    next_shield = min(max_shield, shield + 25)
    raw["shield"] = next_shield
    return max(0, next_shield - shield)


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


def planet_native_beam_tech(defense: int) -> int:
    """Return corpus-verified native planet beam tech from defense posts."""

    dp = max(0, int(defense))
    if dp <= 0:
        return 0
    return max(1, min(10, _round_sqrt_ratio(dp, 2)))


__all__ = [
    "federation_recover_shields",
    "planet_native_beam_tech",
]
