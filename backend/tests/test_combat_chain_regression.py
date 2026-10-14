import unittest

from app.scripts.combat_chain_regression import (
    _expected_next_shield,
    _summary_key_for_status,
    _transition_comparison,
)


class CombatChainRegressionTests(unittest.TestCase):
    def test_non_federation_shield_carries_exactly(self) -> None:
        self.assertEqual(
            _expected_next_shield(
                race_id=3,
                terminal_shield=61,
                terminal_damage=12,
            ),
            61,
        )

    def test_federation_candidate_uses_current_sequence_recovery_rule(self) -> None:
        self.assertEqual(
            _expected_next_shield(
                race_id=1,
                terminal_shield=60,
                terminal_damage=10,
            ),
            70,
        )
        self.assertEqual(
            _expected_next_shield(
                race_id=1,
                terminal_shield=95,
                terminal_damage=20,
            ),
            80,
        )

    def test_transition_matches_exact_carry_and_federation_shield_rule(self) -> None:
        comparison = _transition_comparison(
            {
                "race_id": 1,
                "terminal": {
                    "shield": 60,
                    "damage": 10,
                    "crew": 100,
                    "torpedoes": 4,
                    "fighters": 8,
                    "destroyed": False,
                    "captured": False,
                },
            },
            {
                "start": {
                    "shield": 70,
                    "damage": 10,
                    "crew": 100,
                    "torpedos": 4,
                    "fighters": 8,
                }
            },
        )

        self.assertEqual(comparison["status"], "match")
        self.assertEqual(comparison["carry_mismatches"], [])
        self.assertTrue(comparison["shield"]["matches"])
        self.assertTrue(comparison["shield"]["federation_race_rule_candidate"])

    def test_transition_reports_carry_mismatch_without_collapsing_unknowns(self) -> None:
        comparison = _transition_comparison(
            {
                "race_id": 4,
                "terminal": {
                    "shield": 42,
                    "damage": 20,
                    "crew": 200,
                    "torpedoes": 3,
                    "fighters": 0,
                    "destroyed": False,
                    "captured": False,
                },
            },
            {
                "start": {
                    "shield": 42,
                    "damage": 20,
                    "crew": 190,
                    "fighters": 0,
                }
            },
        )

        self.assertEqual(comparison["status"], "mismatch")
        self.assertEqual(comparison["carry_mismatches"], ["crew"])
        self.assertIsNone(comparison["carry"]["torpedoes"]["matches"])

    def test_reappearance_after_replay_defeat_is_reported_separately(self) -> None:
        comparison = _transition_comparison(
            {
                "race_id": 7,
                "terminal": {
                    "destroyed": True,
                    "captured": False,
                },
            },
            {"start": {"shield": 100}},
        )

        self.assertEqual(comparison["status"], "reappearance_after_defeat")

    def test_summary_status_mapping_matches_public_counter_names(self) -> None:
        self.assertEqual(_summary_key_for_status("match"), "matches")
        self.assertEqual(_summary_key_for_status("mismatch"), "mismatches")
        self.assertEqual(
            _summary_key_for_status("not_comparable"),
            "not_comparable",
        )
        self.assertEqual(
            _summary_key_for_status("reappearance_after_defeat"),
            "reappearance_after_defeat",
        )
        self.assertIsNone(_summary_key_for_status("unknown"))


if __name__ == "__main__":
    unittest.main()
