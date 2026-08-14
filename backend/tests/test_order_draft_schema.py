import unittest

from pydantic import ValidationError

from app.schemas.order_draft import ShipOrderDraftUpsertRequest


class ShipOrderDraftSchemaTests(unittest.TestCase):
    def test_warp_only_is_valid(self) -> None:
        request = ShipOrderDraftUpsertRequest(warp=9)
        self.assertEqual(request.warp, 9)
        self.assertIsNone(request.waypoint_x)

    def test_waypoint_pair_is_valid(self) -> None:
        request = ShipOrderDraftUpsertRequest(
            waypoint_x=1763,
            waypoint_y=2155,
        )
        self.assertEqual((request.waypoint_x, request.waypoint_y), (1763, 2155))

    def test_intercept_order_is_valid(self) -> None:
        request = ShipOrderDraftUpsertRequest(
            warp=9,
            movement_mode="intercept",
            intercept_target_ship_id=48,
        )
        self.assertEqual(request.movement_mode, "intercept")
        self.assertEqual(request.intercept_target_ship_id, 48)

    def test_waypoint_mode_can_be_saved_without_waypoint_change(self) -> None:
        request = ShipOrderDraftUpsertRequest(movement_mode="waypoint")
        self.assertEqual(request.movement_mode, "waypoint")

    def test_intercept_without_target_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ShipOrderDraftUpsertRequest(movement_mode="intercept")

    def test_intercept_target_without_mode_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ShipOrderDraftUpsertRequest(intercept_target_ship_id=48)

    def test_waypoint_mode_with_intercept_target_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ShipOrderDraftUpsertRequest(
                movement_mode="waypoint",
                intercept_target_ship_id=48,
            )

    def test_partial_waypoint_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ShipOrderDraftUpsertRequest(waypoint_x=1763)

    def test_empty_draft_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ShipOrderDraftUpsertRequest()

    def test_warp_above_nine_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ShipOrderDraftUpsertRequest(warp=10)


if __name__ == "__main__":
    unittest.main()
