import unittest

from app.services.movement_intercept import (
    InterceptMode,
    InterceptOrder,
    InterceptStatus,
    Point,
    resolve_intercepts,
)


class MovementInterceptTests(unittest.TestCase):
    def test_invalid_or_hidden_target_stays_put(self):
        result = resolve_intercepts(
            [
                InterceptOrder(
                    ship_id=10,
                    origin=Point(0, 0),
                    target_ship_id=20,
                    max_distance=81,
                    target_visible=False,
                )
            ],
            prior_final_positions={20: Point(40, 0)},
            mode=InterceptMode.CLASSIC,
        )[10]

        self.assertEqual(result.status, InterceptStatus.FAILED_INVALID_TARGET)
        self.assertEqual(result.position, Point(0, 0))
        self.assertEqual(result.moved_distance, 0.0)

    def test_visible_target_without_post_move_position_is_unresolved(self):
        result = resolve_intercepts(
            [
                InterceptOrder(
                    ship_id=10,
                    origin=Point(0, 0),
                    target_ship_id=20,
                    max_distance=81,
                    target_visible=True,
                )
            ],
            prior_final_positions={},
            mode=InterceptMode.CHAINED,
        )[10]

        self.assertEqual(result.status, InterceptStatus.UNRESOLVED_TARGET)
        self.assertIsNone(result.position)
        self.assertFalse(result.certain)

    def test_interceptor_uses_post_move_most_target_position(self):
        result = resolve_intercepts(
            [
                InterceptOrder(
                    ship_id=10,
                    origin=Point(0, 0),
                    target_ship_id=50,
                    max_distance=81,
                )
            ],
            prior_final_positions={50: Point(60, 0)},
            mode=InterceptMode.CLASSIC,
        )[10]

        self.assertEqual(result.status, InterceptStatus.REACHED_TARGET)
        self.assertEqual(result.position, Point(60, 0))
        self.assertEqual(result.target_position, Point(60, 0))

    def test_classic_low_id_sees_higher_interceptor_before_it_moves(self):
        results = resolve_intercepts(
            [
                InterceptOrder(
                    ship_id=10,
                    origin=Point(0, 0),
                    target_ship_id=20,
                    max_distance=100,
                ),
                InterceptOrder(
                    ship_id=20,
                    origin=Point(40, 0),
                    target_ship_id=90,
                    max_distance=100,
                ),
            ],
            prior_final_positions={90: Point(80, 0)},
            mode=InterceptMode.CLASSIC,
        )

        self.assertEqual(results[10].position, Point(40, 0))
        self.assertEqual(results[20].position, Point(80, 0))

    def test_classic_high_id_follows_lower_interceptor_after_it_moves(self):
        results = resolve_intercepts(
            [
                InterceptOrder(
                    ship_id=10,
                    origin=Point(40, 0),
                    target_ship_id=90,
                    max_distance=100,
                ),
                InterceptOrder(
                    ship_id=20,
                    origin=Point(0, 0),
                    target_ship_id=10,
                    max_distance=100,
                ),
            ],
            prior_final_positions={90: Point(80, 0)},
            mode=InterceptMode.CLASSIC,
        )

        self.assertEqual(results[10].position, Point(80, 0))
        self.assertEqual(results[20].position, Point(80, 0))

    def test_chained_interceptor_waits_for_intercepting_target(self):
        results = resolve_intercepts(
            [
                InterceptOrder(
                    ship_id=10,
                    origin=Point(0, 0),
                    target_ship_id=20,
                    max_distance=100,
                ),
                InterceptOrder(
                    ship_id=20,
                    origin=Point(40, 0),
                    target_ship_id=90,
                    max_distance=100,
                ),
            ],
            prior_final_positions={90: Point(80, 0)},
            mode=InterceptMode.CHAINED,
        )

        self.assertEqual(results[20].position, Point(80, 0))
        self.assertEqual(results[10].position, Point(80, 0))

    def test_chained_interceptor_uses_targets_post_move_transform(self):
        def snap_to_planet(position: Point, moved: float) -> Point:
            self.assertGreater(moved, 0.0)
            self.assertEqual(position, Point(80, 0))
            return Point(83, 0)

        results = resolve_intercepts(
            [
                InterceptOrder(
                    ship_id=10,
                    origin=Point(0, 0),
                    target_ship_id=20,
                    max_distance=100,
                ),
                InterceptOrder(
                    ship_id=20,
                    origin=Point(40, 0),
                    target_ship_id=90,
                    max_distance=100,
                    post_move_transform=snap_to_planet,
                ),
            ],
            prior_final_positions={90: Point(80, 0)},
            mode=InterceptMode.CHAINED,
        )

        self.assertEqual(results[20].pre_final_position, Point(80, 0))
        self.assertEqual(results[20].position, Point(83, 0))
        self.assertEqual(results[10].target_position, Point(83, 0))
        self.assertEqual(results[10].position, Point(83, 0))

    def test_unresolved_post_move_transform_fails_closed(self):
        result = resolve_intercepts(
            [
                InterceptOrder(
                    ship_id=10,
                    origin=Point(0, 0),
                    target_ship_id=50,
                    max_distance=81,
                    post_move_transform=lambda _position, _moved: None,
                )
            ],
            prior_final_positions={50: Point(60, 0)},
            mode=InterceptMode.CLASSIC,
        )[10]

        self.assertEqual(result.status, InterceptStatus.UNRESOLVED_POST_MOVE)
        self.assertIsNone(result.position)
        self.assertEqual(result.pre_final_position, Point(60, 0))
        self.assertFalse(result.certain)

    def test_chained_invalid_target_can_anchor_following_ship(self):
        results = resolve_intercepts(
            [
                InterceptOrder(
                    ship_id=10,
                    origin=Point(0, 0),
                    target_ship_id=20,
                    max_distance=100,
                ),
                InterceptOrder(
                    ship_id=20,
                    origin=Point(40, 0),
                    target_ship_id=90,
                    max_distance=100,
                    target_visible=False,
                ),
            ],
            prior_final_positions={90: Point(80, 0)},
            mode=InterceptMode.CHAINED,
        )

        self.assertEqual(
            results[20].status,
            InterceptStatus.FAILED_INVALID_TARGET,
        )
        self.assertEqual(results[20].position, Point(40, 0))
        self.assertEqual(results[10].position, Point(40, 0))

    def test_chained_valid_cycle_is_fail_closed(self):
        results = resolve_intercepts(
            [
                InterceptOrder(
                    ship_id=10,
                    origin=Point(0, 0),
                    target_ship_id=20,
                    max_distance=100,
                ),
                InterceptOrder(
                    ship_id=20,
                    origin=Point(40, 0),
                    target_ship_id=10,
                    max_distance=100,
                ),
            ],
            prior_final_positions={},
            mode=InterceptMode.CHAINED,
        )

        self.assertEqual(
            results[10].status,
            InterceptStatus.UNRESOLVED_CHAINED_CYCLE,
        )
        self.assertEqual(
            results[20].status,
            InterceptStatus.UNRESOLVED_CHAINED_CYCLE,
        )
        self.assertIsNone(results[10].position)
        self.assertIsNone(results[20].position)
        self.assertFalse(results[10].certain)

    def test_movement_is_truncated_by_available_distance(self):
        result = resolve_intercepts(
            [
                InterceptOrder(
                    ship_id=10,
                    origin=Point(0, 0),
                    target_ship_id=50,
                    max_distance=25,
                )
            ],
            prior_final_positions={50: Point(100, 0)},
            mode=InterceptMode.CLASSIC,
        )[10]

        self.assertEqual(result.status, InterceptStatus.MOVED)
        self.assertEqual(result.position, Point(25, 0))
        self.assertEqual(result.requested_distance, 100.0)
        self.assertEqual(result.moved_distance, 25.0)


if __name__ == "__main__":
    unittest.main()
