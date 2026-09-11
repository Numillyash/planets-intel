from __future__ import annotations

from typing import Any, Mapping

from app.services import battle_simulator as _implementation
from app.services import battle_simulator_planet as _planet_implementation
from app.services.battle_simulator_verified_rules import (
    federation_recover_shields,
    planet_native_beam_tech,
)
from app.services.vcr_replay import ReplayUnsupported


def _build_payload(
    *,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    seed: int,
) -> dict[str, Any]:
    """Build one standalone Nu combat payload with side rules enforced.

    Lizard race identity is deliberately preserved for planet combat. The core
    classic engine uses the Lizard 150% in-combat endurance, while its
    planet-result path destroys a Lizard ship at >=100% after the engagement.
    This matches Nu's tidal-force rule and still lets the ship survive long
    enough to capture the planet before being lost.
    """

    if int(left.get("hull_id", 0)) <= 0:
        raise ReplayUnsupported(
            "planetary combatants can only occupy the right/defending side"
        )
    if bool(right.get("galactic_power")):
        raise ReplayUnsupported(
            "Galactic Power forces this Evil Empire Gorbie to the left side; "
            "swap sides or disable the advantage for this scenario"
        )

    return {
        "id": 0,
        "turn": 0,
        "seed": seed,
        "battletype": 1,
        "leftownerid": left.get("owner_id"),
        "rightownerid": right.get("owner_id"),
        "left": _implementation._combatant_payload(left),
        "right": _implementation._combatant_payload(right),
    }


# The implementation's run functions resolve these helpers from their module
# globals at call time. Install the authoritative runtime rules once when this
# facade is imported. This keeps one production path while the large simulator
# service continues to be decomposed into smaller mechanics modules.
_implementation._build_payload = _build_payload
_implementation._fed_recover_shields = federation_recover_shields
_planet_implementation.planet_native_beam_tech = planet_native_beam_tech

run_battle_simulator_once = _implementation.run_battle_simulator_once
run_battle_simulator_odds = _implementation.run_battle_simulator_odds
run_battle_simulator_sequence_once = _implementation.run_battle_simulator_sequence_once
run_battle_simulator_sequence_odds = _implementation.run_battle_simulator_sequence_odds

__all__ = [
    "_build_payload",
    "run_battle_simulator_once",
    "run_battle_simulator_odds",
    "run_battle_simulator_sequence_once",
    "run_battle_simulator_sequence_odds",
]
