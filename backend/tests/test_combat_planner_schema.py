import unittest

from app.schemas.combat_planner import BattleSimulatorCombatant


BASE = {
    "source_kind": "manual",
    "source_id": 1,
    "name": "test",
    "object_id": None,
    "owner_id": None,
    "race_id": 3,
    "hull_id": 10,
    "has_starbase": False,
    "physical_beam_count": 0,
    "physical_launcher_count": 0,
    "physical_bay_count": 0,
    "federation_crew_bonus": False,
    "lizard_crew_bonus": False,
    "galactic_power": False,
    "beam_count": 0,
    "launcher_count": 0,
    "bay_count": 0,
    "beam_id": 0,
    "torpedo_id": 0,
    "shield": 100,
    "damage": 0,
    "crew": 100,
    "mass": 100,
    "torpedoes": 0,
    "fighters": 0,
    "beam_kill_rate": 1,
    "beam_charge_rate": 1,
    "torp_charge_rate": 1,
    "torp_miss_rate": 35,
    "crew_defense_rate": 0,
    "planet_defense": None,
    "starbase_defense": None,
    "starbase_fighters": None,
    "starbase_beam_tech": None,
    "starbase_damage": None,
    "starbase_mass_bonus": None,
    "notes": [],
}


class CombatPlannerSchemaTests(unittest.TestCase):
    def test_federation_bonus_is_required_by_race(self) -> None:
        model = BattleSimulatorCombatant.model_validate(
            {**BASE, "race_id": 1, "federation_crew_bonus": False}
        )
        self.assertTrue(model.federation_crew_bonus)
        self.assertFalse(model.lizard_crew_bonus)

    def test_lizard_bonus_is_required_by_race(self) -> None:
        model = BattleSimulatorCombatant.model_validate(
            {**BASE, "race_id": 2, "lizard_crew_bonus": False}
        )
        self.assertFalse(model.federation_crew_bonus)
        self.assertTrue(model.lizard_crew_bonus)

    def test_non_empire_race_cannot_keep_galactic_power(self) -> None:
        model = BattleSimulatorCombatant.model_validate(
            {**BASE, "race_id": 3, "galactic_power": True}
        )
        self.assertFalse(model.galactic_power)

    def test_robot_starbase_mass_bonus_is_suppressed(self) -> None:
        model = BattleSimulatorCombatant.model_validate(
            {
                **BASE,
                "source_kind": "known_planet",
                "race_id": 9,
                "hull_id": 0,
                "has_starbase": True,
                "planet_defense": 20,
                "starbase_defense": 50,
                "starbase_fighters": 10,
                "starbase_beam_tech": 10,
                "starbase_damage": 0,
                "starbase_mass_bonus": 200,
            }
        )
        self.assertEqual(model.starbase_mass_bonus, 0)
        self.assertFalse(model.federation_crew_bonus)
        self.assertFalse(model.lizard_crew_bonus)


if __name__ == "__main__":
    unittest.main()
