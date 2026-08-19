import unittest

from app.scripts.compare_player_timing_across_games import (
    TimingSample,
    canonical_username,
    cross_game_pairs,
    histogram_overlap,
    hourly_histogram,
    is_reliable_username,
    parse_utc_offset,
)


class CrossGamePlayerTimingTests(unittest.TestCase):
    def test_username_matching_is_case_and_space_insensitive(self) -> None:
        self.assertEqual(canonical_username("  Helping   Die "), "helping die")

    def test_activity_state_placeholders_are_not_usernames(self) -> None:
        for value in ("dead", "OPEN", " ready ", "unopened", "computer", "unknown", "empty"):
            self.assertFalse(is_reliable_username(value))
        self.assertTrue(is_reliable_username("helping die"))
        self.assertTrue(is_reliable_username("georgul"))

    def test_utc_offset_parser(self) -> None:
        self.assertEqual(parse_utc_offset("+03:00"), 180)
        self.assertEqual(parse_utc_offset("-05:30"), -330)

    def test_hourly_histogram_preserves_multiple_daily_modes(self) -> None:
        hist = hourly_histogram([8 * 60 + 5, 8 * 60 + 50, 21 * 60 + 10])
        self.assertEqual(hist[8], 2)
        self.assertEqual(hist[21], 1)
        self.assertEqual(sum(hist), 3)

    def test_histogram_overlap_is_distribution_based(self) -> None:
        self.assertEqual(histogram_overlap([60, 120], [60, 120]), 100.0)
        self.assertEqual(histogram_overlap([60], [120]), 0.0)
        self.assertEqual(histogram_overlap([], [120]), None)

    def test_cross_game_pairs_never_compare_slots_from_same_game(self) -> None:
        samples = [
            TimingSample(100, "A", 1, (60,), ()),
            TimingSample(100, "A", 2, (120,), ()),
            TimingSample(200, "B", 1, (60,), ()),
        ]
        pairs = cross_game_pairs(samples)
        self.assertEqual(len(pairs), 2)
        self.assertTrue(all(left.game_id != right.game_id for left, right in pairs))


if __name__ == "__main__":
    unittest.main()
