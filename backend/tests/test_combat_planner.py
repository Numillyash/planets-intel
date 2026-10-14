import unittest

from app.services.combat_replay_trace import (
    CLASSIC_START_SEEDS,
    _summarize_seed_results,
    apply_combat_scenario_overrides,
)
from app.services.vcr_replay import ReplayUnsupported


class CombatPlannerScenarioTests(unittest.TestCase):
    def test_overrides_clone_payload_without_mutating_fact(self) -> None:
        payload = {
            "seed": 17,
            "left": {"fighters": 80, "torpedos": 12, "name": "Left"},
            "right": {"fighters": 192, "torpedos": 0, "name": "Right"},
        }

        scenario, applied = apply_combat_scenario_overrides(
            payload,
            left={"fighters": 120, "torpedoes": None},
            right={"fighters": 250, "torpedoes": 7},
        )

        self.assertEqual(payload["left"]["fighters"], 80)
        self.assertEqual(payload["right"]["fighters"], 192)
        self.assertEqual(payload["right"]["torpedos"], 0)
        self.assertEqual(scenario["left"]["fighters"], 120)
        self.assertEqual(scenario["left"]["torpedos"], 12)
        self.assertEqual(scenario["right"]["fighters"], 250)
        self.assertEqual(scenario["right"]["torpedos"], 7)
        self.assertEqual(
            applied,
            {
                "left": {"fighters": 120},
                "right": {"fighters": 250, "torpedoes": 7},
            },
        )

    def test_zero_is_a_real_scenario_value(self) -> None:
        payload = {
            "left": {"fighters": 10, "torpedos": 10},
            "right": {"fighters": 10, "torpedos": 10},
        }

        scenario, applied = apply_combat_scenario_overrides(
            payload,
            left={"fighters": 0, "torpedoes": 0},
            right={"fighters": None, "torpedoes": None},
        )

        self.assertEqual(scenario["left"]["fighters"], 0)
        self.assertEqual(scenario["left"]["torpedos"], 0)
        self.assertEqual(applied["left"], {"fighters": 0, "torpedoes": 0})

    def test_missing_side_fails_closed(self) -> None:
        with self.assertRaises(ReplayUnsupported):
            apply_combat_scenario_overrides(
                {"left": {"fighters": 1, "torpedos": 1}},
                left={"fighters": None, "torpedoes": None},
                right={"fighters": 1, "torpedoes": None},
            )

    def test_classic_seed_space_contains_118_documented_starts(self) -> None:
        self.assertEqual(len(CLASSIC_START_SEEDS), 118)
        self.assertEqual(CLASSIC_START_SEEDS[0], 1)
        self.assertEqual(CLASSIC_START_SEEDS[-1], 118)

    def test_seed_summary_reports_frequency_without_probability_claim(self) -> None:
        trials = [
            {
                "start_seed": 1,
                "result": ["right_destroyed"],
                "left": {
                    "destroyed": False,
                    "captured": False,
                    "survived": True,
                    "shield": 50,
                    "damage": 10,
                    "crew": 100,
                    "torpedoes": 5,
                    "fighters": 0,
                },
                "right": {
                    "destroyed": True,
                    "captured": False,
                    "survived": False,
                    "shield": 0,
                    "damage": 105,
                    "crew": 50,
                    "torpedoes": 0,
                    "fighters": 0,
                },
            },
            {
                "start_seed": 2,
                "result": ["left_destroyed"],
                "left": {
                    "destroyed": True,
                    "captured": False,
                    "survived": False,
                    "shield": 0,
                    "damage": 101,
                    "crew": 40,
                    "torpedoes": 0,
                    "fighters": 0,
                },
                "right": {
                    "destroyed": False,
                    "captured": False,
                    "survived": True,
                    "shield": 20,
                    "damage": 60,
                    "crew": 80,
                    "torpedoes": 2,
                    "fighters": 0,
                },
            },
        ]

        summary = _summarize_seed_results(trials)

        self.assertEqual(summary["sample_count"], 2)
        self.assertEqual(summary["sides"]["left"]["survival_seed_frequency_percent"], 50.0)
        self.assertEqual(summary["sides"]["right"]["survival_seed_frequency_percent"], 50.0)
        self.assertEqual(summary["seed_space"]["assumption"], "seed_frequency_is_reported_without_asserting_host_seed_uniformity")


if __name__ == "__main__":
    unittest.main()
