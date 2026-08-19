import unittest
from datetime import datetime, timedelta, timezone

from app.services.player_activity import (
    _activity_state,
    _canonical_activity_username,
    _group_unambiguous_human_slot_keys,
    _minute_samples,
    _player_turn_status,
    _usable_activity_username,
)


class PlayerActivityStateTests(unittest.TestCase):
    def test_player_numeric_viewed_beats_stale_unopened_marker(self) -> None:
        self.assertEqual(
            _activity_state(
                marker="_",
                turn_ready=False,
                player_turn_status=1,
                player_status=1,
            ),
            "open",
        )

    def test_compact_viewed_beats_stale_numeric_unopened(self) -> None:
        self.assertEqual(
            _activity_state(
                marker="o",
                turn_ready=False,
                player_turn_status=0,
                player_status=1,
            ),
            "open",
        )

    def test_ready_fact_has_priority_over_progress_fields(self) -> None:
        self.assertEqual(
            _activity_state(
                marker="_",
                turn_ready=True,
                player_turn_status=0,
                player_status=1,
            ),
            "ready",
        )

    def test_completed_race_marker_is_ready_even_without_turnready_flag(self) -> None:
        self.assertEqual(
            _activity_state(
                marker="3",
                turn_ready=False,
                player_turn_status=0,
                player_status=1,
            ),
            "ready_marker",
        )

    def test_dead_player_stays_dead_despite_stale_progress_fields(self) -> None:
        self.assertEqual(
            _activity_state(
                marker="o",
                turn_ready=True,
                player_turn_status=2,
                player_status=0,
            ),
            "dead",
        )

    def test_missing_progress_is_unknown_not_unopened(self) -> None:
        self.assertEqual(
            _activity_state(
                marker=None,
                turn_ready=False,
                player_turn_status=None,
                player_status=1,
            ),
            "unknown",
        )

    def test_boolean_player_turnstatus_is_not_treated_as_integer(self) -> None:
        self.assertIsNone(_player_turn_status(True))
        self.assertIsNone(_player_turn_status(False))
        self.assertEqual(_player_turn_status(0), 0)
        self.assertEqual(_player_turn_status(2), 2)

    def test_minute_samples_keep_separate_morning_and_evening_modes(self) -> None:
        samples = [
            datetime(2026, 8, 1, 6, 15, tzinfo=timezone.utc),
            datetime(2026, 8, 2, 18, 45, tzinfo=timezone.utc),
            datetime(
                2026,
                8,
                3,
                9,
                30,
                tzinfo=timezone(timedelta(hours=3)),
            ),
        ]
        self.assertEqual(_minute_samples(samples), [375, 1125, 390])

    def test_cross_game_username_normalization_matches_cli_rules(self) -> None:
        self.assertEqual(
            _canonical_activity_username("  Helping   Die "),
            "helping die",
        )
        self.assertFalse(_usable_activity_username("dead"))
        self.assertFalse(_usable_activity_username(" Open "))
        self.assertTrue(_usable_activity_username("Helping Die"))

    def test_cross_game_grouping_keeps_only_unambiguous_human_slots(self) -> None:
        grouped = _group_unambiguous_human_slot_keys(
            [
                (100, 1, "Helping Die", 5),
                (200, 4, " helping  die ", 5),
                (300, 2, "Helping Die", 5),
                (300, 7, "HELPING DIE", 5),
                (400, 3, "dead", 5),
                (500, 1, "Computer", 101),
            ]
        )
        self.assertEqual(
            grouped,
            {"helping die": [(100, 1), (200, 4)]},
        )


if __name__ == "__main__":
    unittest.main()
