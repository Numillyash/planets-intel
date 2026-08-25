import unittest

from app.scripts.combat_lizard_rule_sensitivity import (
    _lizard_ship_sides,
    _neutralize_lizard_identity,
    _sensitivity,
)


class CombatLizardRuleSensitivityTests(unittest.TestCase):
    def test_lizard_ship_sides_requires_ship_and_race_two(self) -> None:
        payload = {
            "left": {"hullid": 10, "raceid": 2},
            "right": {"hullid": 0, "raceid": 2},
        }

        self.assertEqual(_lizard_ship_sides(payload), ["left"])

    def test_neutralizer_changes_only_lizard_ship_race_identity(self) -> None:
        payload = {
            "seed": 5,
            "left": {
                "hullid": 10,
                "raceid": 2,
                "damage": 40,
                "fighters": 3,
            },
            "right": {
                "hullid": 20,
                "raceid": 9,
                "damage": 0,
                "fighters": 7,
            },
        }

        neutral = _neutralize_lizard_identity(payload)

        self.assertEqual(neutral["left"]["raceid"], 0)
        self.assertEqual(neutral["left"]["damage"], 40)
        self.assertEqual(neutral["left"]["fighters"], 3)
        self.assertEqual(neutral["right"], payload["right"])
        self.assertEqual(payload["left"]["raceid"], 2)

    def test_sensitivity_detects_outcome_change(self) -> None:
        factual = {
            "result": ["right_destroyed"],
            "left": {
                "shield": 0,
                "damage": 120,
                "crew": 50,
                "torpedoes": 0,
                "fighters": 0,
                "destroyed": False,
                "captured": False,
                "survived": True,
            },
            "right": {
                "shield": 0,
                "damage": 100,
                "crew": 0,
                "torpedoes": 0,
                "fighters": 0,
                "destroyed": True,
                "captured": False,
                "survived": False,
            },
        }
        neutral = {
            **factual,
            "result": ["left_destroyed"],
        }

        comparison = _sensitivity(factual, neutral)

        self.assertTrue(comparison["sensitive"])
        self.assertTrue(comparison["outcome_changed"])

    def test_sensitivity_detects_terminal_only_change(self) -> None:
        factual = {
            "result": ["right_destroyed"],
            "left": {
                "shield": 0,
                "damage": 90,
                "crew": 50,
                "torpedoes": 0,
                "fighters": 0,
                "destroyed": False,
                "captured": False,
                "survived": True,
            },
            "right": {
                "shield": 0,
                "damage": 100,
                "crew": 0,
                "torpedoes": 0,
                "fighters": 0,
                "destroyed": True,
                "captured": False,
                "survived": False,
            },
        }
        neutral = {
            "result": ["right_destroyed"],
            "left": {**factual["left"], "damage": 95},
            "right": dict(factual["right"]),
        }

        comparison = _sensitivity(factual, neutral)

        self.assertTrue(comparison["sensitive"])
        self.assertFalse(comparison["outcome_changed"])
        self.assertTrue(comparison["left_terminal_changed"])

    def test_identical_replays_are_insensitive(self) -> None:
        replay = {
            "result": ["timeout"],
            "left": {
                "shield": 100,
                "damage": 0,
                "crew": 100,
                "torpedoes": 0,
                "fighters": 0,
                "destroyed": False,
                "captured": False,
                "survived": True,
            },
            "right": {
                "shield": 100,
                "damage": 0,
                "crew": 100,
                "torpedoes": 0,
                "fighters": 0,
                "destroyed": False,
                "captured": False,
                "survived": True,
            },
        }

        comparison = _sensitivity(replay, replay)

        self.assertFalse(comparison["sensitive"])
        self.assertFalse(comparison["outcome_changed"])


if __name__ == "__main__":
    unittest.main()
