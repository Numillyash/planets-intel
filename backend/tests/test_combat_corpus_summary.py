import unittest

from app.scripts.combat_corpus_summary import _compact


class CombatCorpusSummaryTests(unittest.TestCase):
    def test_compact_keeps_counts_and_drops_samples_and_hulls(self) -> None:
        report = {
            "filters": {"game_id": None},
            "summary": {"unique_vcrs": 145},
            "battle_shapes": {"ship_vs_ship": 100, "ship_vs_planet": 45},
            "mechanics": {
                "carrier_battle": {"count": 70, "samples": [{"vcr_id": 1}]},
                "lizard_ship_battle": {"count": 9, "samples": []},
            },
            "races": {
                "2": {
                    "ship_side_appearances": 11,
                    "ship_battles": 9,
                    "carrier_side_appearances": 0,
                    "planet_side_appearances": 3,
                    "samples": [{"vcr_id": 2}],
                }
            },
            "hulls": [{"hull_id": 22}],
        }

        compact = _compact(report)

        self.assertEqual(compact["summary"], {"unique_vcrs": 145})
        self.assertEqual(compact["mechanic_counts"]["carrier_battle"], 70)
        self.assertEqual(compact["mechanic_counts"]["lizard_ship_battle"], 9)
        self.assertEqual(
            compact["race_counts"]["2"],
            {
                "ship_side_appearances": 11,
                "ship_battles": 9,
                "carrier_side_appearances": 0,
                "planet_side_appearances": 3,
            },
        )
        self.assertNotIn("mechanics", compact)
        self.assertNotIn("hulls", compact)
        self.assertNotIn("samples", compact["race_counts"]["2"])


if __name__ == "__main__":
    unittest.main()
