import unittest

from app.services.movement_fuel_policy import (
    WaypointFuelStatus,
    resolve_waypoint_fuel,
)


HULLS = [{"id": 10, "mass": 900, "fighterbays": 0}]
ENGINES = [{"id": 1, "warp9": 1620}]


def payload(*, fuel: int, supplies: int) -> dict:
    return {
        "engineid": 1,
        "beams": 0,
        "tubes": 0,
        "ammo": 0,
        "neutronium": fuel,
        "supplies": supplies,
        "clans": 0,
        "duranium": 0,
        "tritanium": 0,
        "molybdenum": 0,
    }


def resolve(
    *,
    fuel: int,
    supplies: int,
    target_x: int = 60,
    requested: float = 60.0,
    moved: float = 60.0,
    max_distance: float = 81.0,
    speed_multiplier: float = 1.0,
):
    return resolve_waypoint_fuel(
        unlimited_fuel=False,
        payload=payload(fuel=fuel, supplies=supplies),
        hull_id=10,
        owner_observed=True,
        hulls=HULLS,
        beams=[],
        torpedoes=[],
        engines=ENGINES,
        warp=9,
        speed_multiplier=speed_multiplier,
        origin_x=0,
        origin_y=0,
        target_x=target_x,
        target_y=0,
        requested_distance=requested,
        geometric_moved_distance=moved,
        geometric_max_distance=max_distance,
    )


class MovementFuelPolicyTests(unittest.TestCase):
    def test_positive_insufficient_fuel_uses_verified_proration(self) -> None:
        result = resolve(fuel=11, supplies=89)
        self.assertEqual(result.status, WaypointFuelStatus.LIMITED)
        self.assertEqual(result.movement_mass, 1000)
        self.assertEqual(result.fuel_required, 12)
        self.assertEqual(result.fuel_used, 11)
        self.assertEqual((result.override_x, result.override_y), (55, 0))
        self.assertEqual(result.override_moved_distance, 55.0)
        self.assertTrue(result.certain)

    def test_planets_lab_verified_60ly_11_of_12_reference_vector(self) -> None:
        """Mirror the exact reference vector locked in planets-lab fuel v6.

        planets-lab validates a 200-KT ship with Warp-9 fuel factor 8100:
        a 60 ly waypoint needs 12 KT, so 11 KT yields a 55 ly Host endpoint.
        Keep this vector here so production fuel arithmetic cannot drift from
        the independently researched rule layer.
        """

        result = resolve_waypoint_fuel(
            unlimited_fuel=False,
            payload={
                "engineid": 1,
                "beams": 0,
                "tubes": 0,
                "ammo": 0,
                "neutronium": 11,
                "supplies": 89,
                "clans": 0,
                "duranium": 0,
                "tritanium": 0,
                "molybdenum": 0,
            },
            hull_id=10,
            owner_observed=True,
            hulls=[{"id": 10, "mass": 100, "fighterbays": 0}],
            beams=[],
            torpedoes=[],
            engines=[{"id": 1, "warp9": 8100}],
            warp=9,
            speed_multiplier=1.0,
            origin_x=0,
            origin_y=0,
            target_x=60,
            target_y=0,
            requested_distance=60.0,
            geometric_moved_distance=60.0,
            geometric_max_distance=81.0,
        )

        self.assertEqual(result.status, WaypointFuelStatus.LIMITED)
        self.assertEqual(result.movement_mass, 200)
        self.assertEqual(result.fuel_available, 11)
        self.assertEqual(result.fuel_factor, 8100)
        self.assertEqual(result.fuel_required, 12)
        self.assertEqual(result.fuel_used, 11)
        self.assertEqual((result.override_x, result.override_y), (55, 0))
        self.assertEqual(result.override_moved_distance, 55.0)
        self.assertTrue(result.certain)

    def test_sufficient_fuel_keeps_geometric_endpoint(self) -> None:
        result = resolve(fuel=12, supplies=88)
        self.assertEqual(result.status, WaypointFuelStatus.SUFFICIENT)
        self.assertEqual(result.fuel_required, 12)
        self.assertEqual(result.fuel_used, 12)
        self.assertFalse(result.has_position_override)
        self.assertFalse(result.fuel_limited)

    def test_zero_fuel_is_known_but_not_guessed(self) -> None:
        result = resolve(fuel=0, supplies=100)
        self.assertEqual(result.status, WaypointFuelStatus.UNSUPPORTED_ZERO_FUEL)
        self.assertEqual(result.fuel_available, 0)
        self.assertFalse(result.certain)
        self.assertFalse(result.has_position_override)

    def test_shortage_on_partial_waypoint_is_fail_closed(self) -> None:
        result = resolve(
            fuel=11,
            supplies=89,
            target_x=100,
            requested=100.0,
            moved=81.0,
        )
        self.assertEqual(
            result.status,
            WaypointFuelStatus.UNSUPPORTED_PARTIAL_WAYPOINT,
        )
        self.assertFalse(result.certain)

    def test_shortage_on_gravitonic_move_is_fail_closed(self) -> None:
        result = resolve(
            fuel=5,
            supplies=95,
            max_distance=162.0,
            speed_multiplier=2.0,
        )
        self.assertEqual(result.status, WaypointFuelStatus.UNSUPPORTED_GRAVITONIC)
        self.assertFalse(result.certain)

    def test_unlimited_fuel_bypasses_mass_reconstruction(self) -> None:
        result = resolve_waypoint_fuel(
            unlimited_fuel=True,
            payload={},
            hull_id=None,
            owner_observed=False,
            hulls=[],
            beams=[],
            torpedoes=[],
            engines=[],
            warp=9,
            speed_multiplier=1.0,
            origin_x=0,
            origin_y=0,
            target_x=60,
            target_y=0,
            requested_distance=60.0,
            geometric_moved_distance=60.0,
            geometric_max_distance=81.0,
        )
        self.assertEqual(result.status, WaypointFuelStatus.UNLIMITED)
        self.assertTrue(result.certain)

    def test_missing_mass_fact_is_unknown_not_zero(self) -> None:
        raw = payload(fuel=11, supplies=89)
        raw.pop("supplies")
        result = resolve_waypoint_fuel(
            unlimited_fuel=False,
            payload=raw,
            hull_id=10,
            owner_observed=True,
            hulls=HULLS,
            beams=[],
            torpedoes=[],
            engines=ENGINES,
            warp=9,
            speed_multiplier=1.0,
            origin_x=0,
            origin_y=0,
            target_x=60,
            target_y=0,
            requested_distance=60.0,
            geometric_moved_distance=60.0,
            geometric_max_distance=81.0,
        )
        self.assertEqual(result.status, WaypointFuelStatus.UNKNOWN)
        self.assertIsNone(result.movement_mass)
        self.assertIn("supplies", result.mass_reason or "")


if __name__ == "__main__":
    unittest.main()
