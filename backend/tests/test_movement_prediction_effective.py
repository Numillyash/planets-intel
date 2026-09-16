import unittest
from types import SimpleNamespace

from app.services.movement_prediction_effective import _append_missing_tow_items


HULLS = [{"id": 10, "name": "Tow Test Hull", "engines": 2}]


def ship(
    ship_id: int,
    *,
    owner_id: int = 3,
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
        x=0,
        y=0,
        warp=9,
        payload=payload,
    )


def catalog(*, unlimited_fuel: bool):
    return SimpleNamespace(
        settings={
            "unlimitedfuel": unlimited_fuel,
            "gravitywells": False,
        },
        hulls=HULLS,
        beams=[],
        torpedos=[],
        engines=[],
    )


class EffectiveMovementPredictionTests(unittest.TestCase):
    def test_factual_tow_without_local_drafts_emits_both_participants(self) -> None:
        result = _append_missing_tow_items(
            {"items": []},
            ships=[
                ship(1, mission=6, target_id=2, waypoint_x=60),
                ship(2, waypoint_x=10),
            ],
            drafts=[],
            catalog=catalog(unlimited_fuel=True),
            planets=[],
            owner_slot_id=3,
        )

        items = {item["ship_id"]: item for item in result["items"]}
        self.assertEqual(set(items), {1, 2})
        self.assertEqual(items[1]["tow_role"], "tower")
        self.assertEqual(items[2]["tow_role"], "target")
        self.assertEqual(items[1]["tow_target_ship_id"], 2)
        self.assertEqual(items[2]["tow_tower_ship_id"], 1)
        self.assertEqual(items[1]["predicted_x"], 60.0)
        self.assertEqual(items[2]["predicted_x"], 60.0)
        self.assertIsNone(items[1]["blocker_class"])
        self.assertIsNone(items[2]["blocker_class"])

    def test_finite_fuel_factual_tow_is_visible_but_fail_closed(self) -> None:
        result = _append_missing_tow_items(
            {"items": []},
            ships=[
                ship(1, mission=6, target_id=2, waypoint_x=60),
                ship(2, waypoint_x=10),
            ],
            drafts=[],
            catalog=catalog(unlimited_fuel=False),
            planets=[],
            owner_slot_id=3,
        )

        items = {item["ship_id"]: item for item in result["items"]}
        self.assertEqual(set(items), {1, 2})
        self.assertFalse(items[1]["certain"])
        self.assertFalse(items[2]["certain"])
        self.assertIsNone(items[1]["predicted_x"])
        self.assertIsNone(items[2]["predicted_x"])
        self.assertEqual(items[1]["fuel_status"], "unresolved_tow")
        self.assertEqual(items[1]["blocker_class"], "phase_state_required")
        self.assertEqual(items[2]["blocker_class"], "phase_state_required")

    def test_existing_tower_item_is_not_duplicated_but_target_is_added(self) -> None:
        existing = {"ship_id": 1, "marker": "draft-row"}
        result = _append_missing_tow_items(
            {"items": [existing]},
            ships=[
                ship(1, mission=6, target_id=2, waypoint_x=60),
                ship(2, waypoint_x=10),
            ],
            drafts=[],
            catalog=catalog(unlimited_fuel=True),
            planets=[],
            owner_slot_id=3,
        )

        self.assertEqual([item["ship_id"] for item in result["items"]], [1, 2])
        self.assertEqual(result["items"][0]["marker"], "draft-row")
        self.assertEqual(result["items"][1]["tow_role"], "target")


if __name__ == "__main__":
    unittest.main()
