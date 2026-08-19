import unittest
from datetime import datetime, timedelta, timezone

from app.services.player_activity import (
    _activity_state,
    _minute_samples,
    _player_turn_status,
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


if __name__ == "__main__":
    unittest.main()
