import unittest

from app.scripts.compare_player_timing_across_games import (
    canonical_username,
    histogram_overlap,
    hourly_histogram,
    parse_utc_offset,
)


class CrossGamePlayerTimingTests(unittest.TestCase):
    def test_username_matching_is_case_and_space_insensitive(self) -> None:
        self.assertEqual(canonical_username("  Helping   Die "), "helping die")

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


if __name__ == "__main__":
    unittest.main()
