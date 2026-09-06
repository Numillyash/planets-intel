import unittest
from types import SimpleNamespace

from app.services.movement_intercept import (
    InterceptMode,
    InterceptOrder,
    InterceptStatus,
    Point,
)
from app.services.movement_prediction_runtime import (
    _CONTEXT,
    _FuelContext,
    _build_tow_outcomes,
    _resolve_intercepts,
)
from app.services.movement_warp_well import PlanetWarpWell


HULLS = [{"id": 10, "name": "Tow Test Hull", "engines": 2}]
HULL_NAMES = {10: "Tow Test Hull"}


def ship(
    ship_id: int,
    *,
    owner_id: int = 3,
    warp: int = 9,
    x: int = 0,
    y: int = 0,
    mission: int | None = None,
    target_id: int | None = None,
    waypoint_x: int = 10,
    waypoint_y: int = 0,
):
    payload = {
        "waypointx": waypoint_x,
        "waypointy": waypoint_y,
        "neutronium": 100,
    }
    if mission is not None:
        payload["mission"] = mission
    if target_id is not None:
        payload["mission1target"] = target_id
    return SimpleNamespace(
        ship_id=ship_id,
        owner_id=owner_id,
        hull_id=10,
        x=x,
        y=y,
        warp=warp,
        payload=payload,
    )


def draft(
    ship_id: int,
    *,
    mission: str | None = None,
    warp: int | None = None,
    waypoint_x: int | None = None,
    waypoint_y: int | None = None,
    tow_target_ship_id: int | None = None,
):
    return SimpleNamespace(
        ship_id=ship_id,
        mission=mission,
        warp=warp,
        waypoint_x=waypoint_x,
        waypoint_y=waypoint_y,
        tow_target_ship_id=tow_target_ship_id,
    )


class MovementPredictionTowRuntimeTests(unittest.TestCase):
    def test_unlimited_locked_tow_reserves_shared_endpoint(self) -> None:
        ships = [
            ship(1, mission=6, target_id=2, waypoint_x=60),
            ship(2, waypoint_x=10),
        ]
        outcomes, known = _build_tow_outcomes(
            ships=ships,
            drafts=[],
            owner_slot_id=3,
            hulls=HULLS,
            hull_names=HULL_NAMES,
            unlimited_fuel=True,
            gravity_wells_enabled=False,
            planet_wells=[],
        )

        self.assertEqual(outcomes[1].status, "locked")
        self.assertEqual(outcomes[1].role, "tower")
        self.assertEqual(outcomes[2].status, "towed")
        self.assertEqual(outcomes[2].role, "target")
        self.assertTrue(outcomes[1].certain)
        self.assertTrue(outcomes[2].certain)
        self.assertEqual(known[1], Point(60.0, 0.0))
        self.assertEqual(known[2], Point(60.0, 0.0))

    def test_explicit_local_tow_target_resolves_without_factual_tow(self) -> None:
        ships = [
            ship(1, waypoint_x=60),
            ship(2, waypoint_x=10),
        ]
        outcomes, known = _build_tow_outcomes(
            ships=ships,
            drafts=[draft(1, mission="Try to Tow", tow_target_ship_id=2)],
            owner_slot_id=3,
            hulls=HULLS,
            hull_names=HULL_NAMES,
            unlimited_fuel=True,
            gravity_wells_enabled=False,
            planet_wells=[],
        )

        self.assertEqual(outcomes[1].status, "locked")
        self.assertEqual(outcomes[2].status, "towed")
        self.assertEqual(outcomes[1].target_ship_id, 2)
        self.assertEqual(known[2], Point(60.0, 0.0))

    def test_explicit_local_tow_target_overrides_factual_target(self) -> None:
        ships = [
            ship(1, mission=6, target_id=2, waypoint_x=60),
            ship(2, waypoint_x=10),
            ship(3, waypoint_x=10),
        ]
        outcomes, known = _build_tow_outcomes(
            ships=ships,
            drafts=[draft(1, mission="Try to Tow", tow_target_ship_id=3)],
            owner_slot_id=3,
            hulls=HULLS,
            hull_names=HULL_NAMES,
            unlimited_fuel=True,
            gravity_wells_enabled=False,
            planet_wells=[],
        )

        self.assertEqual(outcomes[1].target_ship_id, 3)
        self.assertEqual(outcomes[3].status, "towed")
        self.assertNotIn(2, outcomes)
        self.assertEqual(known[3], Point(60.0, 0.0))

    def test_finite_fuel_tow_blocks_later_movement_fail_closed(self) -> None:
        ships = [
            ship(1, mission=6, target_id=2, waypoint_x=60),
            ship(2, waypoint_x=10),
        ]
        outcomes, known = _build_tow_outcomes(
            ships=ships,
            drafts=[],
            owner_slot_id=3,
            hulls=HULLS,
            hull_names=HULL_NAMES,
            unlimited_fuel=False,
            gravity_wells_enabled=False,
            planet_wells=[],
        )

        self.assertEqual(outcomes[1].lock_status, "unknown")
        self.assertFalse(outcomes[1].certain)
        self.assertFalse(outcomes[2].certain)
        self.assertEqual(known, {})
        self.assertIn("withheld", outcomes[1].reason)

    def test_local_mission_override_can_cancel_factual_tow(self) -> None:
        ships = [
            ship(1, mission=6, target_id=2, waypoint_x=60),
            ship(2, waypoint_x=10),
        ]
        outcomes, known = _build_tow_outcomes(
            ships=ships,
            drafts=[draft(1, mission="Exploration")],
            owner_slot_id=3,
            hulls=HULLS,
            hull_names=HULL_NAMES,
            unlimited_fuel=True,
            gravity_wells_enabled=False,
            planet_wells=[],
        )

        self.assertEqual(outcomes, {})
        self.assertEqual(known, {})

    def test_new_local_tow_without_explicit_target_stays_unresolved(self) -> None:
        ships = [
            ship(1, waypoint_x=60),
            ship(2, waypoint_x=10),
        ]
        outcomes, known = _build_tow_outcomes(
            ships=ships,
            drafts=[draft(1, mission="Try to Tow")],
            owner_slot_id=3,
            hulls=HULLS,
            hull_names=HULL_NAMES,
            unlimited_fuel=True,
            gravity_wells_enabled=False,
            planet_wells=[],
        )

        self.assertEqual(outcomes[1].status, "draft_tow_target_unresolved")
        self.assertFalse(outcomes[1].certain)
        self.assertEqual(known, {})

    def test_all_nonfuel_four_fingers_true_stays_unresolved(self) -> None:
        ships = [
            ship(1, mission=6, target_id=2, warp=9, waypoint_x=60),
            ship(2, warp=9, waypoint_x=100),
        ]
        outcomes, known = _build_tow_outcomes(
            ships=ships,
            drafts=[],
            owner_slot_id=3,
            hulls=HULLS,
            hull_names=HULL_NAMES,
            unlimited_fuel=True,
            gravity_wells_enabled=False,
            planet_wells=[],
        )

        self.assertEqual(outcomes[1].lock_status, "unknown")
        self.assertFalse(outcomes[1].certain)
        self.assertEqual(known, {})

    def test_tow_warp_well_interaction_fails_closed(self) -> None:
        ships = [
            ship(1, mission=6, target_id=2, waypoint_x=60),
            ship(2, waypoint_x=10),
        ]
        outcomes, known = _build_tow_outcomes(
            ships=ships,
            drafts=[],
            owner_slot_id=3,
            hulls=HULLS,
            hull_names=HULL_NAMES,
            unlimited_fuel=True,
            gravity_wells_enabled=True,
            planet_wells=[
                PlanetWarpWell(
                    planet_id=99,
                    name="Tow Well",
                    position=Point(60.0, 0.0),
                )
            ],
        )

        self.assertEqual(outcomes[1].lock_status, "locked")
        self.assertEqual(outcomes[1].status, "locked_route_unresolved")
        self.assertFalse(outcomes[1].certain)
        self.assertEqual(outcomes[1].warp_well.status.value, "captured")
        self.assertEqual(known, {})

    def test_intercept_uses_known_post_tow_target_position(self) -> None:
        ships = [
            ship(1, mission=6, target_id=2, waypoint_x=60),
            ship(2, waypoint_x=10),
            ship(3, x=0, y=20, waypoint_x=0, waypoint_y=20),
        ]
        outcomes, known = _build_tow_outcomes(
            ships=ships,
            drafts=[],
            owner_slot_id=3,
            hulls=HULLS,
            hull_names=HULL_NAMES,
            unlimited_fuel=True,
            gravity_wells_enabled=False,
            planet_wells=[],
        )
        context = _FuelContext(
            owner_slot_id=3,
            unlimited_fuel=True,
            ships={item.ship_id: item for item in ships},
            hulls=HULLS,
            beams=[],
            torpedoes=[],
            engines=[],
            tow_outcomes=outcomes,
            tow_known_positions=known,
        )
        token = _CONTEXT.set(context)
        try:
            results = _resolve_intercepts(
                [
                    InterceptOrder(
                        ship_id=3,
                        origin=Point(0.0, 20.0),
                        target_ship_id=2,
                        max_distance=81.0,
                        target_visible=True,
                    )
                ],
                prior_final_positions={},
                mode=InterceptMode.CLASSIC,
            )
        finally:
            _CONTEXT.reset(token)

        self.assertEqual(results[3].status, InterceptStatus.REACHED_TARGET)
        self.assertEqual(results[3].position, Point(60.0, 0.0))
        self.assertTrue(results[3].certain)


if __name__ == "__main__":
    unittest.main()
