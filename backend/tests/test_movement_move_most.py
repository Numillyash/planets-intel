import math
import unittest

from app.services.movement_intercept import Point
from app.services.movement_move_most import (
    MoveMostOrder,
    MoveMostStatus,
    maximum_distance,
    resolve_move_most_order,
)


class MovementMoveMostTests(unittest.TestCase):
    def test_warp_nine_normal_speed_is_eighty_one_ly(self) -> None:
        self.assertEqual(maximum_distance(9), 81.0)

    def test_gravitonic_speed_doubles_normal_distance(self) -> None:
        self.assertEqual(maximum_distance(9, speed_multiplier=2.0), 162.0)

    def test_reaches_near_waypoint_exactly(self) -> None:
        result = resolve_move_most_order(
            MoveMostOrder(
                ship_id=7,
                origin=Point(0, 0),
                waypoint=Point(30, 40),
                warp=9,
            )
        )
        self.assertEqual(result.status, MoveMostStatus.REACHED_WAYPOINT)
        self.assertEqual(result.position, Point(30, 40))
        self.assertEqual(result.moved_distance, 50.0)
        self.assertTrue(result.reached_waypoint)

    def test_truncates_long_waypoint_to_warp_squared_distance(self) -> None:
        result = resolve_move_most_order(
            MoveMostOrder(
                ship_id=8,
                origin=Point(0, 0),
                waypoint=Point(300, 400),
                warp=6,
            )
        )
        self.assertEqual(result.status, MoveMostStatus.MOVED)
        self.assertAlmostEqual(result.moved_distance or 0.0, 36.0)
        self.assertAlmostEqual(result.position.x if result.position else -1, 21.6)
        self.assertAlmostEqual(result.position.y if result.position else -1, 28.8)
        self.assertFalse(result.reached_waypoint)

    def test_warp_zero_stays_put(self) -> None:
        result = resolve_move_most_order(
            MoveMostOrder(
                ship_id=9,
                origin=Point(10, 12),
                waypoint=Point(50, 50),
                warp=0,
            )
        )
        self.assertEqual(result.status, MoveMostStatus.STAYED_NO_SPEED)
        self.assertEqual(result.position, Point(10, 12))
        self.assertEqual(result.moved_distance, 0.0)

    def test_no_waypoint_stays_put(self) -> None:
        result = resolve_move_most_order(
            MoveMostOrder(
                ship_id=10,
                origin=Point(10, 12),
                waypoint=None,
                warp=9,
            )
        )
        self.assertEqual(result.status, MoveMostStatus.STAYED_NO_WAYPOINT)
        self.assertEqual(result.position, Point(10, 12))

    def test_ineligible_ship_is_fail_closed(self) -> None:
        result = resolve_move_most_order(
            MoveMostOrder(
                ship_id=11,
                origin=Point(1, 2),
                waypoint=Point(100, 100),
                warp=9,
                eligible=False,
                ineligible_reason="Tow phase owns this ship.",
            )
        )
        self.assertEqual(result.status, MoveMostStatus.UNRESOLVED_INELIGIBLE)
        self.assertIsNone(result.position)
        self.assertFalse(result.certain)

    def test_diagonal_distance_is_not_axis_clamped(self) -> None:
        result = resolve_move_most_order(
            MoveMostOrder(
                ship_id=12,
                origin=Point(100, 100),
                waypoint=Point(181, 181),
                warp=9,
            )
        )
        self.assertEqual(result.status, MoveMostStatus.MOVED)
        self.assertAlmostEqual(result.moved_distance or 0.0, 81.0)
        self.assertAlmostEqual(
            math.hypot(
                (result.position.x if result.position else 100) - 100,
                (result.position.y if result.position else 100) - 100,
            ),
            81.0,
        )


if __name__ == "__main__":
    unittest.main()
