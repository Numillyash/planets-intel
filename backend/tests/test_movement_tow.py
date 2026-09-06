import unittest

from app.services.movement_tow import (
    TowAttempt,
    TowLockStatus,
    TowShipState,
    hull_engine_count,
    payload_is_tow_mission,
    payload_tow_target_id,
    resolve_strict_tow_locks,
)


def ship(
    ship_id: int,
    *,
    x: int = 100,
    y: int = 100,
    warp: int = 9,
    waypoint_x: int = 110,
    waypoint_y: int = 100,
    fuel: int | None = 100,
    engines: int | None = 2,
    speed_multiplier: float | None = 1.0,
) -> TowShipState:
    return TowShipState(
        ship_id=ship_id,
        x=x,
        y=y,
        warp=warp,
        waypoint_x=waypoint_x,
        waypoint_y=waypoint_y,
        fuel=fuel,
        engine_count=engines,
        speed_multiplier=speed_multiplier,
    )


class MovementTowTests(unittest.TestCase):
    def test_payload_tow_contract_uses_nu_mission_and_target_fields(self) -> None:
        payload = {"mission": 6, "mission1target": 42}
        self.assertTrue(payload_is_tow_mission(payload))
        self.assertEqual(payload_tow_target_id(payload), 42)
        self.assertEqual(payload_tow_target_id({"mission1_target_id": "43"}), 43)
        self.assertFalse(payload_is_tow_mission({"mission": 7}))

    def test_hull_engine_count_accepts_catalog_aliases(self) -> None:
        hulls = [
            {"id": 16, "engines": 2},
            {"id": 17, "enginecount": 1},
        ]
        self.assertEqual(hull_engine_count(hull_id=16, hulls=hulls), 2)
        self.assertEqual(hull_engine_count(hull_id=17, hulls=hulls), 1)
        self.assertIsNone(hull_engine_count(hull_id=18, hulls=hulls))

    def test_unlimited_short_waypoint_locks_without_target_fuel(self) -> None:
        states = {1: ship(1, fuel=None), 2: ship(2, fuel=None)}
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[TowAttempt(1, 2)],
            unlimited_fuel=True,
        )
        self.assertEqual(resolution.attempts[0].status, TowLockStatus.LOCKED)
        self.assertTrue(resolution.attempts[0].certain)

    def test_unlimited_single_engine_target_locks_without_target_fuel(self) -> None:
        states = {
            1: ship(1, fuel=None),
            2: ship(2, fuel=None, engines=1, waypoint_x=200),
        }
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[TowAttempt(1, 2)],
            unlimited_fuel=True,
        )
        self.assertEqual(resolution.attempts[0].status, TowLockStatus.LOCKED)

    def test_unlimited_slower_target_locks_without_target_fuel(self) -> None:
        states = {
            1: ship(1, warp=9, fuel=None),
            2: ship(2, warp=8, waypoint_x=200, fuel=None),
        }
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[TowAttempt(1, 2)],
            unlimited_fuel=True,
        )
        self.assertEqual(resolution.attempts[0].status, TowLockStatus.LOCKED)

    def test_all_nonfuel_four_fingers_true_with_zero_snapshot_fuel_is_unknown(self) -> None:
        states = {
            1: ship(1, warp=7, fuel=100),
            2: ship(2, warp=7, waypoint_x=160, fuel=0),
        }
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[TowAttempt(1, 2)],
            unlimited_fuel=True,
        )
        self.assertEqual(resolution.attempts[0].status, TowLockStatus.UNKNOWN)
        self.assertFalse(resolution.attempts[0].certain)
        self.assertIn("target-fuel", resolution.attempts[0].reason)

    def test_all_nonfuel_four_fingers_true_with_positive_snapshot_fuel_is_unknown(self) -> None:
        states = {
            1: ship(1, warp=7, fuel=100),
            2: ship(2, warp=7, waypoint_x=160, fuel=26),
        }
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[TowAttempt(1, 2)],
            unlimited_fuel=True,
        )
        self.assertEqual(resolution.attempts[0].status, TowLockStatus.UNKNOWN)
        self.assertFalse(resolution.attempts[0].certain)

    def test_finite_fuel_zero_snapshot_fuel_stays_unknown(self) -> None:
        states = {1: ship(1, fuel=0), 2: ship(2, fuel=None)}
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[TowAttempt(1, 2)],
        )
        self.assertEqual(resolution.attempts[0].status, TowLockStatus.UNKNOWN)
        self.assertFalse(resolution.attempts[0].certain)
        self.assertIn("Tow-phase fuel", resolution.attempts[0].reason)

    def test_finite_fuel_positive_snapshot_fuel_stays_unknown(self) -> None:
        states = {1: ship(1, fuel=100), 2: ship(2, fuel=0)}
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[TowAttempt(1, 2)],
        )
        self.assertEqual(resolution.attempts[0].status, TowLockStatus.UNKNOWN)
        self.assertIn("combined towing mass", resolution.attempts[0].reason)

    def test_single_engine_tower_still_fails_certainly(self) -> None:
        states = {1: ship(1, engines=1, fuel=0), 2: ship(2, fuel=None)}
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[TowAttempt(1, 2)],
        )
        self.assertEqual(
            resolution.attempts[0].status,
            TowLockStatus.INSUFFICIENT_ENGINES,
        )
        self.assertTrue(resolution.attempts[0].certain)

    def test_non_colocated_target_fails(self) -> None:
        states = {1: ship(1), 2: ship(2, x=101)}
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[TowAttempt(1, 2)],
            unlimited_fuel=True,
        )
        self.assertEqual(
            resolution.attempts[0].status,
            TowLockStatus.TARGET_NOT_COLOCATED,
        )

    def test_unknown_nonfuel_break_input_stays_unknown(self) -> None:
        states = {
            1: ship(1),
            2: ship(2, fuel=None, waypoint_x=200, engines=None),
        }
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[TowAttempt(1, 2)],
            unlimited_fuel=True,
        )
        self.assertEqual(resolution.attempts[0].status, TowLockStatus.UNKNOWN)
        self.assertFalse(resolution.attempts[0].certain)

    def test_same_target_contest_is_ambiguous_not_ship_id_resolved(self) -> None:
        states = {1: ship(1), 2: ship(2), 3: ship(3)}
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[TowAttempt(1, 3), TowAttempt(2, 3)],
            unlimited_fuel=True,
        )
        self.assertEqual(
            [item.status for item in resolution.attempts],
            [TowLockStatus.AMBIGUOUS_CONTEST, TowLockStatus.AMBIGUOUS_CONTEST],
        )
        self.assertEqual(resolution.successful, ())

    def test_tow_chain_fails_closed_for_whole_connected_topology(self) -> None:
        states = {1: ship(1), 2: ship(2), 3: ship(3)}
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[TowAttempt(1, 2), TowAttempt(2, 3)],
            unlimited_fuel=True,
        )
        self.assertEqual(
            [item.status for item in resolution.attempts],
            [TowLockStatus.UNSUPPORTED_CHAIN, TowLockStatus.UNSUPPORTED_CHAIN],
        )
        self.assertTrue(all(not item.certain for item in resolution.attempts))

    def test_tow_chain_does_not_poison_independent_component(self) -> None:
        states = {
            1: ship(1),
            2: ship(2),
            3: ship(3),
            10: ship(10),
            11: ship(11, fuel=None),
        }
        resolution = resolve_strict_tow_locks(
            ships=states,
            attempts=[
                TowAttempt(1, 2),
                TowAttempt(2, 3),
                TowAttempt(10, 11),
            ],
            unlimited_fuel=True,
        )
        self.assertEqual(
            [item.status for item in resolution.attempts],
            [
                TowLockStatus.UNSUPPORTED_CHAIN,
                TowLockStatus.UNSUPPORTED_CHAIN,
                TowLockStatus.LOCKED,
            ],
        )
        self.assertFalse(resolution.attempts[0].certain)
        self.assertFalse(resolution.attempts[1].certain)
        self.assertTrue(resolution.attempts[2].certain)


if __name__ == "__main__":
    unittest.main()
