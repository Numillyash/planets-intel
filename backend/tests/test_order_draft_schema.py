import unittest

from pydantic import ValidationError

from app.schemas.order_draft import (
    PlanetOrderDraftUpsertRequest,
    ShipOrderDraftUpsertRequest,
    StarbaseOrderDraftUpsertRequest,
)


class ShipOrderDraftSchemaTests(unittest.TestCase):
    def test_warp_only_is_valid(self) -> None:
        request = ShipOrderDraftUpsertRequest(warp=9)
        self.assertEqual(request.warp, 9)
        self.assertIsNone(request.waypoint_x)

    def test_waypoint_pair_is_valid(self) -> None:
        request = ShipOrderDraftUpsertRequest(waypoint_x=1763, waypoint_y=2155)
        self.assertEqual((request.waypoint_x, request.waypoint_y), (1763, 2155))

    def test_intercept_order_is_valid(self) -> None:
        request = ShipOrderDraftUpsertRequest(
            warp=9,
            movement_mode="intercept",
            intercept_target_ship_id=48,
        )
        self.assertEqual(request.movement_mode, "intercept")
        self.assertEqual(request.intercept_target_ship_id, 48)

    def test_tow_target_is_valid_without_overloading_movement_mode(self) -> None:
        request = ShipOrderDraftUpsertRequest(
            mission="Try to Tow",
            tow_target_ship_id=77,
        )
        self.assertEqual(request.mission, "Try to Tow")
        self.assertEqual(request.tow_target_ship_id, 77)
        self.assertIsNone(request.movement_mode)

    def test_waypoint_mode_can_be_saved_without_waypoint_change(self) -> None:
        request = ShipOrderDraftUpsertRequest(movement_mode="waypoint")
        self.assertEqual(request.movement_mode, "waypoint")

    def test_ship_mission_enemy_and_friendly_code_are_valid(self) -> None:
        request = ShipOrderDraftUpsertRequest(
            mission="Mine Sweep",
            primary_enemy_id=7,
            friendly_code="msc",
        )
        self.assertEqual(request.mission, "Mine Sweep")
        self.assertEqual(request.primary_enemy_id, 7)
        self.assertEqual(request.friendly_code, "msc")

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

    def test_intercept_cannot_carry_tow_target(self) -> None:
        with self.assertRaises(ValidationError):
            ShipOrderDraftUpsertRequest(
                movement_mode="intercept",
                intercept_target_ship_id=48,
                tow_target_ship_id=77,
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

    def test_friendly_code_longer_than_three_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ShipOrderDraftUpsertRequest(friendly_code="abcd")

    def test_unsafe_friendly_code_characters_are_rejected(self) -> None:
        for code in ("a&b", "a<b", "a>b"):
            with self.subTest(code=code), self.assertRaises(ValidationError):
                ShipOrderDraftUpsertRequest(friendly_code=code)


class PlanetOrderDraftSchemaTests(unittest.TestCase):
    def test_planet_friendly_code_is_valid(self) -> None:
        request = PlanetOrderDraftUpsertRequest(friendly_code="NUK")
        self.assertEqual(request.friendly_code, "NUK")

    def test_planet_long_friendly_code_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PlanetOrderDraftUpsertRequest(friendly_code="NUKE")


class StarbaseOrderDraftSchemaTests(unittest.TestCase):
    def test_standard_primary_order_is_valid(self) -> None:
        request = StarbaseOrderDraftUpsertRequest(primary_order="refuel")
        self.assertEqual(request.primary_order, "refuel")

    def test_unknown_primary_order_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StarbaseOrderDraftUpsertRequest(primary_order="teleport")


if __name__ == "__main__":
    unittest.main()
