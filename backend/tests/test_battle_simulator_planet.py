import unittest

from app.services.battle_simulator_planet import (
    _damage_tech,
    apply_planet_carryover,
    planet_bay_count,
    planet_beam_count,
    planet_fighter_count,
    planet_sequence_shape_supported,
    rebuild_planet_combatant,
)


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

    def test_planet_damage_and_fighter_losses_carry_to_next_wave(self) -> None:
        start = rebuild_planet_combatant(
            {
                "hull_id": 0,
                "has_starbase": True,
                "planet_defense": 65,
                "starbase_defense": 100,
                "starbase_fighters": 5,
                "starbase_beam_tech": 10,
                "starbase_damage": 0,
                "starbase_mass_bonus": 0,
                "beam_charge_rate": 1,
            }
        )
        # DP65 generates 8 planetary fighters; plus five base fighters = 13.
        self.assertEqual(start["fighters"], 13)

        carried = apply_planet_carryover(
            start,
            start,
            {
                "shield": 0,
                "damage": 43,
                "fighters": 6,
            },
        )

        # 7 fighters lost: 5 base fighters first, then 2 planetary fighters.
        # Host planet DP damage loss = TRUNC(65*43/100)=27, so 65-27-2=36.
        self.assertEqual(carried["planet_defense"], 36)
        self.assertEqual(carried["starbase_fighters"], 0)
        self.assertEqual(carried["starbase_damage"], 43)
        self.assertEqual(carried["starbase_defense"], 57)
        self.assertEqual(carried["starbase_beam_tech"], 5)
        self.assertEqual(carried["damage"], 0)
        self.assertEqual(carried["shield"], 0)

    def test_base_is_removed_at_one_hundred_accumulated_damage(self) -> None:
        start = rebuild_planet_combatant(
            {
                "hull_id": 0,
                "has_starbase": True,
                "planet_defense": 50,
                "starbase_defense": 100,
                "starbase_fighters": 20,
                "starbase_beam_tech": 10,
                "starbase_damage": 90,
                "starbase_mass_bonus": 200,
                "beam_charge_rate": 1,
            }
        )
        carried = apply_planet_carryover(
            start,
            start,
            {
                "shield": 20,
                "damage": 10,
                "fighters": start["fighters"],
            },
        )

        self.assertFalse(carried["has_starbase"])
        self.assertIsNone(carried["starbase_defense"])
        self.assertIsNone(carried["starbase_damage"])
        self.assertIsNone(carried["starbase_mass_bonus"])
        self.assertEqual(carried["mass"], 145)

    def test_base_tech_reduction_uses_new_battle_damage(self) -> None:
        self.assertEqual(_damage_tech(10, 70), 3)
        self.assertEqual(_damage_tech(7, 70), 2)
        self.assertEqual(_damage_tech(1, 99), 1)

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
