import unittest

from app.services.battle_simulator_planet import (
    apply_planet_carryover,
    planet_bay_count,
    planet_beam_count,
    planet_fighter_count,
    planet_sequence_shape_supported,
    rebuild_planet_combatant,
)
from app.services.vcr_replay import ReplayUnsupported


class BattleSimulatorPlanetTests(unittest.TestCase):
    def test_planet_component_formulas_use_integer_host_rounding(self) -> None:
        self.assertEqual(planet_fighter_count(0), 0)
        self.assertEqual(planet_fighter_count(1), 1)
        self.assertEqual(planet_fighter_count(25), 5)
        self.assertEqual(planet_bay_count(25), 5)
        self.assertEqual(planet_beam_count(25, 50, 0), 5)
        self.assertEqual(planet_beam_count(25, 50, 200), 10)

    def test_rebuild_includes_base_mass_fighters_and_five_bays(self) -> None:
        rebuilt = rebuild_planet_combatant(
            {
                "hull_id": 0,
                "has_starbase": True,
                "planet_defense": 25,
                "starbase_defense": 50,
                "starbase_fighters": 20,
                "starbase_beam_tech": 10,
                "starbase_damage": 0,
                "starbase_mass_bonus": 200,
                "beam_charge_rate": 1,
            }
        )

        self.assertEqual(rebuilt["mass"], 375)
        self.assertEqual(rebuilt["fighters"], 25)
        self.assertEqual(rebuilt["bay_count"], 10)
        self.assertEqual(rebuilt["beam_count"], 10)
        self.assertEqual(rebuilt["beam_id"], 10)

    def test_planet_only_damage_and_fighter_losses_carry_exactly(self) -> None:
        start = rebuild_planet_combatant(
            {
                "hull_id": 0,
                "has_starbase": False,
                "planet_defense": 65,
                "starbase_defense": None,
                "starbase_fighters": None,
                "starbase_beam_tech": None,
                "starbase_damage": None,
                "starbase_mass_bonus": None,
                "beam_charge_rate": 1,
            }
        )
        self.assertEqual(start["fighters"], 8)

        carried = apply_planet_carryover(
            start,
            start,
            {
                "shield": 0,
                "damage": 43,
                "fighters": 6,
            },
        )

        # TRUNC(65*43/100)=27 damage DP plus two destroyed planetary fighters.
        self.assertEqual(carried["planet_defense"], 36)
        self.assertEqual(carried["damage"], 0)
        self.assertEqual(carried["shield"], 0)
        self.assertEqual(carried["fighters"], 6)

    def test_starbase_fighters_carry_when_no_hull_damage_occurred(self) -> None:
        start = rebuild_planet_combatant(
            {
                "hull_id": 0,
                "has_starbase": True,
                "planet_defense": 65,
                "starbase_defense": 100,
                "starbase_fighters": 5,
                "starbase_beam_tech": 10,
                "starbase_damage": 12,
                "starbase_mass_bonus": 0,
                "beam_charge_rate": 1,
            }
        )
        self.assertEqual(start["fighters"], 13)

        carried = apply_planet_carryover(
            start,
            start,
            {
                "shield": 35,
                "damage": 0,
                "fighters": 6,
            },
        )

        # Seven losses consume all five base fighters before two planetary
        # fighters. Those two generated-fighter losses remove two planet DP.
        self.assertEqual(carried["starbase_fighters"], 0)
        self.assertEqual(carried["planet_defense"], 63)
        self.assertEqual(carried["starbase_defense"], 100)
        self.assertEqual(carried["starbase_beam_tech"], 10)
        self.assertEqual(carried["starbase_damage"], 12)
        self.assertEqual(carried["shield"], 35)

    def test_starbase_hull_damage_fails_closed_without_host_formula(self) -> None:
        start = rebuild_planet_combatant(
            {
                "hull_id": 0,
                "has_starbase": True,
                "planet_defense": 65,
                "starbase_defense": 100,
                "starbase_fighters": 5,
                "starbase_beam_tech": 10,
                "starbase_damage": 12,
                "starbase_mass_bonus": 0,
                "beam_charge_rate": 1,
            }
        )

        with self.assertRaisesRegex(
            ReplayUnsupported,
            "exact multi-wave starbase carry-over stops",
        ):
            apply_planet_carryover(
                start,
                start,
                {
                    "shield": 0,
                    "damage": 1,
                    "fighters": start["fighters"],
                },
            )

    def test_robot_starbase_never_gets_shielded_mass_bonus(self) -> None:
        rebuilt = rebuild_planet_combatant(
            {
                "hull_id": 0,
                "race_id": 9,
                "has_starbase": True,
                "planet_defense": 25,
                "starbase_defense": 50,
                "starbase_fighters": 20,
                "starbase_beam_tech": 10,
                "starbase_damage": 0,
                "starbase_mass_bonus": 200,
            }
        )

        self.assertEqual(rebuilt["starbase_mass_bonus"], 0)
        self.assertEqual(rebuilt["mass"], 175)

    def test_only_ship_queue_vs_one_fixed_planet_shape_is_supported(self) -> None:
        ship = {"hull_id": 10}
        planet = {"hull_id": 0}

        self.assertTrue(planet_sequence_shape_supported((ship,), (planet,)))
        self.assertTrue(planet_sequence_shape_supported((ship, ship), (planet,)))
        self.assertTrue(planet_sequence_shape_supported((ship, ship), (ship, ship)))
        self.assertFalse(planet_sequence_shape_supported((planet,), (ship,)))
        self.assertFalse(planet_sequence_shape_supported((ship,), (planet, ship)))
        self.assertFalse(planet_sequence_shape_supported((ship,), (planet, planet)))


if __name__ == "__main__":
    unittest.main()
