import unittest

from app.scripts.combat_planet_chain_regression import (
    _infer_no_starbase_start,
    _projection_check,
    _transition,
)
from app.services.battle_simulator_planet import rebuild_planet_combatant


def _raw_from_planet(combatant: dict) -> dict:
    return {
        "objectid": 50,
        "name": "Test World",
        "hullid": 0,
        "raceid": combatant.get("race_id"),
        "beamcount": combatant["beam_count"],
        "launchercount": combatant["launcher_count"],
        "baycount": combatant["bay_count"],
        "beamid": combatant["beam_id"],
        "torpedoid": combatant["torpedo_id"],
        "shield": combatant["shield"],
        "damage": combatant["damage"],
        "crew": combatant["crew"],
        "mass": combatant["mass"],
        "fighters": combatant["fighters"],
        "hasstarbase": combatant["has_starbase"],
    }


class CombatPlanetChainRegressionTests(unittest.TestCase):
    def test_no_starbase_start_is_inferred_only_from_explicit_false(self) -> None:
        combatant = rebuild_planet_combatant(
            {"hull_id": 0, "race_id": 3, "has_starbase": False, "planet_defense": 65},
            shield=72,
        )
        raw = _raw_from_planet(combatant)
        inferred = _infer_no_starbase_start(raw)
        self.assertIsNotNone(inferred)
        self.assertEqual(inferred["planet_defense"], 65)
        self.assertEqual(_projection_check(inferred, raw)["status"], "match")

        unknown = dict(raw)
        unknown.pop("hasstarbase")
        self.assertIsNone(_infer_no_starbase_start(unknown))

    def test_real_shape_no_starbase_carry_formula_matches_next_vcr_start(self) -> None:
        first = rebuild_planet_combatant(
            {"hull_id": 0, "race_id": 3, "has_starbase": False, "planet_defense": 65}
        )
        next_start = rebuild_planet_combatant(
            {"hull_id": 0, "race_id": 3, "has_starbase": False, "planet_defense": 36},
            shield=0,
        )
        transition = _transition(
            {
                "game_id": 1,
                "turn": 10,
                "planet_id": 50,
                "name": "Test World",
                "position": [1000, 1000],
                "vcr_id": 7,
                "has_starbase": False,
                "start": _raw_from_planet(first),
                "terminal": {
                    "shield": 0,
                    "damage": 43,
                    "fighters": 6,
                    "destroyed": False,
                    "captured": False,
                },
            },
            {
                "vcr_id": 8,
                "start": _raw_from_planet(next_start),
            },
        )
        self.assertEqual(transition["status"], "match")
        self.assertEqual(transition["exact_no_starbase"]["status"], "match")
        self.assertEqual(
            transition["exact_no_starbase"]["predicted_next_planet_defense"],
            36,
        )

    def test_starbase_transition_only_asserts_direct_shield_carry(self) -> None:
        transition = _transition(
            {
                "game_id": 1,
                "turn": 10,
                "planet_id": 50,
                "name": "Base World",
                "position": [1000, 1000],
                "vcr_id": 7,
                "has_starbase": True,
                "start": {"hasstarbase": True, "mass": 300, "shield": 100},
                "terminal": {
                    "shield": 41,
                    "damage": 0,
                    "fighters": 10,
                    "destroyed": False,
                    "captured": False,
                },
            },
            {
                "vcr_id": 8,
                "start": {"hasstarbase": True, "mass": 300, "shield": 41},
            },
        )
        self.assertEqual(transition["status"], "match")
        self.assertEqual(transition["exact_no_starbase"]["status"], "not_applicable")
        self.assertTrue(transition["shield_carry"]["matches"])


if __name__ == "__main__":
    unittest.main()
