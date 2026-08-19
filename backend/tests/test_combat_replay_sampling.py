import unittest

from app.services.combat_replay_sampling import sample_battle_results
from app.services.combat_replay_trace import _summarize_seed_results


class CombatReplaySamplingTests(unittest.TestCase):
    def test_sampling_returns_requested_battle_count(self) -> None:
        seed_results = [
            {"start_seed": 1, "result": ["left_destroyed"]},
            {"start_seed": 2, "result": ["right_destroyed"]},
        ]

        trials = sample_battle_results(
            seed_results,
            battles=10_000,
            sampling_seed=12345,
        )

        self.assertEqual(len(trials), 10_000)
        self.assertTrue(all(trial in seed_results for trial in trials))

    def test_sampling_seed_is_reproducible(self) -> None:
        seed_results = [
            {"start_seed": 1},
            {"start_seed": 2},
            {"start_seed": 3},
        ]

        first = sample_battle_results(
            seed_results,
            battles=50,
            sampling_seed=777,
        )
        second = sample_battle_results(
            seed_results,
            battles=50,
            sampling_seed=777,
        )

        self.assertEqual(first, second)

    def test_sampling_rejects_empty_seed_space(self) -> None:
        with self.assertRaises(ValueError):
            sample_battle_results([], battles=10, sampling_seed=1)

    def test_summary_reports_mean_terminal_combat_state(self) -> None:
        trials = [
            {
                "start_seed": 1,
                "result": ["right_destroyed"],
                "left": {
                    "destroyed": False,
                    "captured": False,
                    "survived": True,
                    "shield": 20,
                    "damage": 40,
                    "crew": 800,
                    "torpedoes": 6,
                    "fighters": 70,
                },
                "right": {
                    "destroyed": True,
                    "captured": False,
                    "survived": False,
                    "shield": 0,
                    "damage": 100,
                    "crew": 500,
                    "torpedoes": 2,
                    "fighters": 20,
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
                    "damage": 100,
                    "crew": 400,
                    "torpedoes": 2,
                    "fighters": 50,
                },
                "right": {
                    "destroyed": False,
                    "captured": False,
                    "survived": True,
                    "shield": 30,
                    "damage": 20,
                    "crew": 900,
                    "torpedoes": 8,
                    "fighters": 60,
                },
            },
        ]

        summary = _summarize_seed_results(trials)
        left = summary["sides"]["left"]
        right = summary["sides"]["right"]

        self.assertEqual(summary["sample_count"], 2)
        self.assertEqual(left["survived_count"], 1)
        self.assertEqual(left["destroyed_count"], 1)
        self.assertEqual(left["survival_seed_frequency_percent"], 50.0)
        self.assertEqual(left["mean_final_shield"], 10.0)
        self.assertEqual(left["mean_final_damage"], 70.0)
        self.assertEqual(left["mean_final_crew"], 600.0)
        self.assertEqual(left["mean_final_torpedoes"], 4.0)
        self.assertEqual(left["mean_final_fighters"], 60.0)

        self.assertEqual(right["survived_count"], 1)
        self.assertEqual(right["destroyed_count"], 1)
        self.assertEqual(right["mean_final_shield"], 15.0)
        self.assertEqual(right["mean_final_damage"], 60.0)
        self.assertEqual(right["mean_final_crew"], 700.0)
        self.assertEqual(right["mean_final_torpedoes"], 5.0)
        self.assertEqual(right["mean_final_fighters"], 40.0)


if __name__ == "__main__":
    unittest.main()
