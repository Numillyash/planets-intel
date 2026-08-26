import unittest

from app.models.ship_observation import ShipObservation
from app.services.movement_intercept import Point
from app.services.movement_move_most import MoveMostOrder
from app.services.movement_prediction_runtime import (
    _CONTEXT,
    _FuelContext,
    _resolve_move_most_order,
)


HULLS = [{"id": 10, "mass": 900, "fighterbays": 0}]
ENGINES = [{"id": 1, "warp9": 1620}]


def ship_payload(*, fuel: int = 11, include_supplies: bool = True) -> dict:
    result = {
        "engineid": 1,
        "beams": 0,
        "tubes": 0,
        "ammo": 0,
        "neutronium": fuel,
        "clans": 0,
        "duranium": 0,
        "tritanium": 0,
        "molybdenum": 0,
    }
    if include_supplies:
        result["supplies"] = 100 - fuel
    return result


def context(payload: dict) -> _FuelContext:
    ship = ShipObservation(
        batch_id=1,
        ship_id=7,
        owner_id=3,
        info_turn=10,
        hull_id=10,
        name="Fuel test ship",
        x=0,
        y=0,
        warp=9,
        payload=payload,
    )
    return _FuelContext(
        owner_slot_id=3,
        unlimited_fuel=False,
        ships={7: ship},
        hulls=HULLS,
        beams=[],
        torpedoes=[],
        engines=ENGINES,
    )


class MovementPredictionRuntimeTests(unittest.TestCase):
    def test_verified_positive_shortage_replaces_move_most_endpoint(self) -> None:
        ctx = context(ship_payload(fuel=11))
        token = _CONTEXT.set(ctx)
        try:
            result = _resolve_move_most_order(
                MoveMostOrder(
                    ship_id=7,
                    origin=Point(0, 0),
                    waypoint=Point(60, 0),
                    warp=9,
                )
            )
        finally:
            _CONTEXT.reset(token)

        self.assertEqual(result.position, Point(55.0, 0.0))
        self.assertEqual(result.moved_distance, 55.0)
        self.assertFalse(result.reached_waypoint)
        self.assertTrue(result.certain)
        self.assertEqual(ctx.resolutions[7].fuel_required, 12)
        self.assertEqual(ctx.resolutions[7].fuel_used, 11)

    def test_unknown_mass_fails_closed_before_warp_well_or_intercept(self) -> None:
        ctx = context(ship_payload(fuel=11, include_supplies=False))
        token = _CONTEXT.set(ctx)
        try:
            result = _resolve_move_most_order(
                MoveMostOrder(
                    ship_id=7,
                    origin=Point(0, 0),
                    waypoint=Point(60, 0),
                    warp=9,
                )
            )
        finally:
            _CONTEXT.reset(token)

        self.assertIsNone(result.position)
        self.assertIsNone(result.moved_distance)
        self.assertIsNone(result.reached_waypoint)
        self.assertFalse(result.certain)
        self.assertEqual(ctx.resolutions[7].status.value, "unknown")

    def test_unlimited_fuel_keeps_geometry(self) -> None:
        ctx = context({})
        ctx.unlimited_fuel = True
        token = _CONTEXT.set(ctx)
        try:
            result = _resolve_move_most_order(
                MoveMostOrder(
                    ship_id=7,
                    origin=Point(0, 0),
                    waypoint=Point(60, 0),
                    warp=9,
                )
            )
        finally:
            _CONTEXT.reset(token)

        self.assertEqual(result.position, Point(60, 0))
        self.assertTrue(result.reached_waypoint)
        self.assertEqual(ctx.resolutions[7].status.value, "unlimited")


if __name__ == "__main__":
    unittest.main()
