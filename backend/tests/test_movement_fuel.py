import unittest

from app.services.movement_fuel import (
    engine_fuel_factor,
    movement_fuel_use,
    movement_mass_from_private_ship,
    project_toward_waypoint,
    prorate_waypoint_distance,
)


HULLS = [
    {"id": 10, "mass": 100, "fighterbays": 0},
    {"id": 11, "mass": 120, "fighterbays": 4},
]
BEAMS = [{"id": 2, "mass": 5}]
TORPEDOES = [{"id": 3, "mass": 8}]
ENGINES = [{"id": 4, "warp1": 100, "warp8": 700, "warp9": 900}]


def base_payload() -> dict:
    return {
        "engineid": 4,
        "beams": 2,
        "beamid": 2,
        "tubes": 3,
        "torpedoid": 3,
        "ammo": 7,
        "neutronium": 50,
        "supplies": 10,
        "clans": 5,
        "duranium": 2,
        "tritanium": 3,
        "molybdenum": 4,
    }


class MovementFuelTests(unittest.TestCase):
    def test_documented_fuel_formula_truncates_mass_and_distance(self) -> None:
        self.assertEqual(
            movement_fuel_use(
                fuel_factor=900,
                total_mass=109,
                distance_traveled=80.99,
                max_distance_per_turn=81,
            ),
            0,
        )
        self.assertEqual(
            movement_fuel_use(
                fuel_factor=9000,
                total_mass=1099,
                distance_traveled=80.99,
                max_distance_per_turn=81,
            ),
            96,
        )

    def test_proration_uses_whole_waypoint_distance(self) -> None:
        result = prorate_waypoint_distance(
            requested_distance=60,
            fuel_available=11,
            fuel_required=12,
        )
        self.assertAlmostEqual(result.ratio, 11 / 12)
        self.assertAlmostEqual(result.distance, 55.0)

    def test_host_projection_rounds_major_axis_then_minor_axis(self) -> None:
        self.assertEqual(
            project_toward_waypoint(
                x=0,
                y=0,
                target_x=100,
                target_y=50,
                distance=55,
            ),
            (49, 25),
        )

    def test_reconstructs_movement_mass_from_factual_components(self) -> None:
        result = movement_mass_from_private_ship(
            payload=base_payload(),
            hull_id=10,
            owner_observed=True,
            hulls=HULLS,
            beams=BEAMS,
            torpedoes=TORPEDOES,
        )
        self.assertTrue(result.available)
        self.assertEqual(result.engine_id, 4)
        self.assertEqual(result.fuel_available, 50)
        self.assertEqual(result.components["hull"], 100)
        self.assertEqual(result.components["beams"], 10)
        self.assertEqual(result.components["torpedo_tubes"], 24)
        self.assertEqual(result.components["torpedoes"], 7)
        self.assertEqual(result.total_mass, 215)

    def test_generic_carrier_ammo_is_fighter_stock_when_unambiguous(self) -> None:
        payload = base_payload()
        payload.update({"beams": 0, "tubes": 0, "ammo": 12})
        payload.pop("beamid")
        payload.pop("torpedoid")
        result = movement_mass_from_private_ship(
            payload=payload,
            hull_id=11,
            owner_observed=True,
            hulls=HULLS,
            beams=BEAMS,
            torpedoes=TORPEDOES,
        )
        self.assertTrue(result.available)
        self.assertEqual(result.components["fighters"], 12)
        self.assertEqual(result.components["torpedoes"], 0)

    def test_missing_cargo_stays_unknown_instead_of_becoming_zero(self) -> None:
        payload = base_payload()
        payload.pop("supplies")
        result = movement_mass_from_private_ship(
            payload=payload,
            hull_id=10,
            owner_observed=True,
            hulls=HULLS,
            beams=BEAMS,
            torpedoes=TORPEDOES,
        )
        self.assertFalse(result.available)
        self.assertIsNone(result.total_mass)
        self.assertIn("supplies", result.reason or "")

    def test_foreign_ship_mass_is_fail_closed_even_if_payload_has_values(self) -> None:
        result = movement_mass_from_private_ship(
            payload=base_payload(),
            hull_id=10,
            owner_observed=False,
            hulls=HULLS,
            beams=BEAMS,
            torpedoes=TORPEDOES,
        )
        self.assertFalse(result.available)
        self.assertIsNone(result.total_mass)

    def test_ambiguous_generic_ammo_does_not_guess(self) -> None:
        payload = base_payload()
        payload.update({"tubes": 1, "ammo": 10})
        result = movement_mass_from_private_ship(
            payload=payload,
            hull_id=11,
            owner_observed=True,
            hulls=HULLS,
            beams=BEAMS,
            torpedoes=TORPEDOES,
        )
        self.assertFalse(result.available)
        self.assertIn("ambiguous", result.reason or "")

    def test_engine_factor_comes_from_selected_warp_column(self) -> None:
        self.assertEqual(engine_fuel_factor(engine_id=4, warp=9, engines=ENGINES), 900)
        self.assertEqual(engine_fuel_factor(engine_id=4, warp=0, engines=ENGINES), 0)
        self.assertIsNone(engine_fuel_factor(engine_id=99, warp=9, engines=ENGINES))


if __name__ == "__main__":
    unittest.main()
