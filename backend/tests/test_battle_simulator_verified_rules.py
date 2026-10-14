from app.services import battle_simulator
from app.services import battle_simulator_planet
from app.services import battle_simulator_runtime  # noqa: F401


def test_runtime_installs_fixed_federation_recovery() -> None:
    ship = {
        "federation_crew_bonus": True,
        "shield": 40,
        "damage": 0,
    }

    recovered = battle_simulator._fed_recover_shields(ship)

    assert recovered == 25
    assert ship["shield"] == 65


def test_federation_recovery_respects_damage_reduced_cap() -> None:
    ship = {
        "federation_crew_bonus": True,
        "shield": 40,
        "damage": 50,
    }

    recovered = battle_simulator._fed_recover_shields(ship)

    assert recovered == 10
    assert ship["shield"] == 50


def test_federation_recovery_matches_high_shield_discriminator() -> None:
    ship = {
        "federation_crew_bonus": True,
        "shield": 84,
        "damage": 0,
    }

    recovered = battle_simulator._fed_recover_shields(ship)

    assert recovered == 16
    assert ship["shield"] == 100


def test_runtime_installs_nearest_native_planet_beam_rounding() -> None:
    expected = {
        0: 0,
        4: 1,
        5: 2,
        12: 2,
        13: 3,
        24: 3,
        25: 4,
        67: 6,
        86: 7,
        148: 9,
    }

    for defense, beam_tech in expected.items():
        assert battle_simulator_planet.planet_native_beam_tech(defense) == beam_tech


def test_rebuild_planet_combatant_uses_verified_beam_rounding() -> None:
    combatant = battle_simulator_planet.rebuild_planet_combatant(
        {
            "hull_id": 0,
            "race_id": 0,
            "has_starbase": False,
            "planet_defense": 67,
        }
    )

    assert combatant["beam_id"] == 6
