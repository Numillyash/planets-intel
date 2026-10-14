import unittest
from collections import Counter

from app.scripts.movement_fuel_runtime_diagnostic import (
    _factual_waypoint,
    _record_status,
)


class MovementFuelRuntimeDiagnosticTests(unittest.TestCase):
    def test_factual_waypoint_requires_both_coordinates(self) -> None:
        self.assertEqual(
            _factual_waypoint({"waypointx": 0, "waypointy": 42}),
            (0, 42),
        )
        self.assertIsNone(_factual_waypoint({"waypointx": 5}))
        self.assertIsNone(_factual_waypoint({"waypointy": 5}))

    def test_factual_waypoint_accepts_known_aliases(self) -> None:
        self.assertEqual(
            _factual_waypoint({"targetx": "12", "targety": "-3"}),
            (12, -3),
        )
        self.assertEqual(
            _factual_waypoint({"waypoint_x": 7, "waypoint_y": 8}),
            (7, 8),
        )

    def test_record_status_keeps_limited_and_unknown_separate(self) -> None:
        counter: Counter[str] = Counter()
        summary = {"limited": 0, "unresolved": 0}

        _record_status(
            counter,
            summary,
            status="limited",
            limited_key="limited",
            unresolved_key="unresolved",
        )
        _record_status(
            counter,
            summary,
            status="unknown",
            limited_key="limited",
            unresolved_key="unresolved",
        )
        _record_status(
            counter,
            summary,
            status="sufficient",
            limited_key="limited",
            unresolved_key="unresolved",
        )

        self.assertEqual(counter, {"limited": 1, "unknown": 1, "sufficient": 1})
        self.assertEqual(summary, {"limited": 1, "unresolved": 1})


if __name__ == "__main__":
    unittest.main()
