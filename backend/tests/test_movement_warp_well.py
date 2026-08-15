import unittest

from app.services.movement_intercept import Point
from app.services.movement_warp_well import (
    PlanetWarpWell,
    WarpWellStatus,
    resolve_warp_well,
)


class WarpWellMovementTests(unittest.TestCase):
    def setUp(self):
        self.planet = PlanetWarpWell(
            planet_id=24,
            name="Taurus",
            position=Point(100.0, 100.0),
        )

    def test_capture_inside_three_light_years(self):
        result = resolve_warp_well(
            ship_id=20,
            pre_well_position=Point(102.5, 100.0),
            warp=9,
            moved_distance=81.0,
            planets=[self.planet],
        )

        self.assertEqual(result.status, WarpWellStatus.CAPTURED)
        self.assertEqual(result.position, Point(100.0, 100.0))
        self.assertEqual(result.planet_id, 24)
        self.assertAlmostEqual(result.distance_to_planet or 0.0, 2.5)
        self.assertTrue(result.certain)

    def test_exact_three_light_year_boundary_captures_normal_ship(self):
        result = resolve_warp_well(
            ship_id=20,
            pre_well_position=Point(103.0, 100.0),
            warp=9,
            moved_distance=81.0,
            planets=[self.planet],
        )

        self.assertEqual(result.status, WarpWellStatus.CAPTURED)
        self.assertEqual(result.position, Point(100.0, 100.0))

    def test_outside_three_light_years_does_not_capture(self):
        endpoint = Point(103.01, 100.0)
        result = resolve_warp_well(
            ship_id=20,
            pre_well_position=endpoint,
            warp=9,
            moved_distance=81.0,
            planets=[self.planet],
        )

        self.assertEqual(result.status, WarpWellStatus.OUTSIDE_WELLS)
        self.assertEqual(result.position, endpoint)
        self.assertIsNone(result.planet_id)

    def test_warp_one_is_not_pulled(self):
        endpoint = Point(102.0, 100.0)
        result = resolve_warp_well(
            ship_id=20,
            pre_well_position=endpoint,
            warp=1,
            moved_distance=1.0,
            planets=[self.planet],
        )

        self.assertEqual(result.status, WarpWellStatus.NOT_APPLICABLE)
        self.assertEqual(result.position, endpoint)

    def test_nonmoving_ship_is_not_pulled(self):
        endpoint = Point(102.0, 100.0)
        result = resolve_warp_well(
            ship_id=20,
            pre_well_position=endpoint,
            warp=9,
            moved_distance=0.0,
            planets=[self.planet],
        )

        self.assertEqual(result.status, WarpWellStatus.NOT_APPLICABLE)
        self.assertEqual(result.position, endpoint)

    def test_multiple_overlapping_wells_fail_closed(self):
        second = PlanetWarpWell(
            planet_id=25,
            name="Cue Ball",
            position=Point(104.0, 100.0),
        )
        result = resolve_warp_well(
            ship_id=20,
            pre_well_position=Point(102.0, 100.0),
            warp=9,
            moved_distance=81.0,
            planets=[self.planet, second],
        )

        self.assertEqual(result.status, WarpWellStatus.UNRESOLVED_MULTIPLE)
        self.assertIsNone(result.position)
        self.assertFalse(result.certain)

    def test_capture_can_make_observed_displacement_exceed_warp_squared(self):
        # The ship flies exactly 81 ly to x=81, which lies 2.4 ly inside a
        # planet's well. Host then places it at the planet at x=83.4.
        planet = PlanetWarpWell(
            planet_id=99,
            name="The Right Planet",
            position=Point(83.4, 0.0),
        )
        result = resolve_warp_well(
            ship_id=20,
            pre_well_position=Point(81.0, 0.0),
            warp=9,
            moved_distance=81.0,
            planets=[planet],
        )

        self.assertEqual(result.status, WarpWellStatus.CAPTURED)
        self.assertEqual(result.position, Point(83.4, 0.0))
        self.assertAlmostEqual(result.distance_to_planet or 0.0, 2.4)


if __name__ == "__main__":
    unittest.main()
