import unittest

from app.scripts.combat_lizard_regression import (
    BASELINES,
    _evaluate_expected,
    _subset_matches,
)


class CombatLizardRegressionTests(unittest.TestCase):
    def test_baseline_keys_are_unique(self) -> None:
        keys = [
            (item["game_id"], item["turn"], item["vcr_id"])
            for item in BASELINES
        ]
        self.assertEqual(len(keys), len(set(keys)))

    def test_subset_matches_only_expected_fields(self) -> None:
        self.assertTrue(
            _subset_matches(
                {"damage": 12, "fighters": 39, "crew": 1724},
                {"damage": 12, "fighters": 39},
            )
        )
        self.assertFalse(
            _subset_matches(
                {"damage": 12, "fighters": 38},
                {"damage": 12, "fighters": 39},
            )
        )

    def test_expected_comparison_accepts_matching_projection(self) -> None:
        comparison = {
            "sensitive": True,
            "outcome_changed": False,
            "factual": {
                "result": ["left_destroyed"],
                "left": {"damage": 154},
                "right": {
                    "shield": 0,
                    "damage": 12,
                    "crew": 1724,
                    "fighters": 39,
                    "survived": True,
                },
            },
            "neutralized_lizard": {
                "result": ["left_destroyed"],
                "left": {"damage": 101},
                "right": {
                    "shield": 0,
                    "damage": 9,
                    "crew": 1732,
                    "fighters": 42,
                    "survived": True,
                },
            },
        }
        expected = BASELINES[0]["expected"]
        self.assertEqual(_evaluate_expected(comparison, expected), [])

    def test_expected_comparison_reports_terminal_regression(self) -> None:
        comparison = {
            "sensitive": True,
            "outcome_changed": False,
            "factual": {
                "result": ["left_destroyed"],
                "left": {},
                "right": {
                    "shield": 0,
                    "damage": 13,
                    "crew": 1724,
                    "fighters": 39,
                    "survived": True,
                },
            },
            "neutralized_lizard": {
                "result": ["left_destroyed"],
                "left": {},
                "right": {
                    "shield": 0,
                    "damage": 9,
                    "crew": 1732,
                    "fighters": 42,
                    "survived": True,
                },
            },
        }
        errors = _evaluate_expected(comparison, BASELINES[0]["expected"])
        self.assertIn("factual_right", errors)


if __name__ == "__main__":
    unittest.main()
