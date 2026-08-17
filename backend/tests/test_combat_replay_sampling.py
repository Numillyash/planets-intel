import unittest

from app.services.combat_replay_sampling import sample_battle_results


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


if __name__ == "__main__":
    unittest.main()
