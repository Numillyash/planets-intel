import unittest

from app.services.historical_track_lifecycle import _segment_track


class HistoricalTrackLifecycleTests(unittest.TestCase):
    def test_defeated_ship_id_reused_by_new_hull_is_split(self):
        track = {
            "ship_id": 20,
            "name": "PATRIOT CLASS LIGHT CARRIER",
            "owner_id": 8,
            "hull_id": 92,
            "first_turn": 9,
            "last_turn": 10,
            "points": [
                {
                    "turn": 9,
                    "gap_from_previous": False,
                    "evidence": "combat",
                    "combat_outcome": "defeated",
                    "post_host_confirmed": False,
                    "combat_event": {
                        "sides": [
                            {
                                "object_kind": "ship",
                                "object_id": 20,
                                "name": "ILL WIND CLASS BATTLECRUISER",
                                "owner_id": 4,
                                "hull_id": 70,
                            },
                            {
                                "object_kind": "planet",
                                "object_id": 99,
                                "name": "Test",
                                "owner_id": 8,
                                "hull_id": None,
                            },
                        ],
                    },
                },
                {
                    "turn": 10,
                    "gap_from_previous": False,
                    "evidence": "scan",
                    "combat_outcome": None,
                    "post_host_confirmed": False,
                    "combat_event": None,
                },
            ],
        }

        segments = _segment_track(track)

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["ship_id"], 20)
        self.assertEqual(segments[0]["first_turn"], 9)
        self.assertEqual(segments[0]["last_turn"], 9)
        self.assertEqual(segments[0]["name"], "ILL WIND CLASS BATTLECRUISER")
        self.assertEqual(segments[0]["owner_id"], 4)
        self.assertEqual(segments[0]["hull_id"], 70)

        self.assertEqual(segments[1]["ship_id"], 20)
        self.assertEqual(segments[1]["first_turn"], 10)
        self.assertEqual(segments[1]["last_turn"], 10)
        self.assertEqual(segments[1]["name"], "PATRIOT CLASS LIGHT CARRIER")
        self.assertEqual(segments[1]["owner_id"], 8)
        self.assertEqual(segments[1]["hull_id"], 92)

    def test_reacquisition_gap_does_not_create_new_identity(self):
        track = {
            "ship_id": 38,
            "name": "LARGE DEEP SPACE FREIGHTER",
            "owner_id": 5,
            "hull_id": 17,
            "first_turn": 8,
            "last_turn": 10,
            "points": [
                {
                    "turn": 8,
                    "gap_from_previous": False,
                    "evidence": "scan",
                    "combat_outcome": None,
                    "post_host_confirmed": False,
                    "combat_event": None,
                },
                {
                    "turn": 10,
                    "gap_from_previous": True,
                    "evidence": "scan",
                    "combat_outcome": None,
                    "post_host_confirmed": False,
                    "combat_event": None,
                },
            ],
        }

        segments = _segment_track(track)

        self.assertEqual(len(segments), 1)
        self.assertEqual(len(segments[0]["points"]), 2)

    def test_observed_hull_change_splits_even_without_defeat_status(self):
        track = {
            "ship_id": 20,
            "name": "PATRIOT CLASS LIGHT CARRIER",
            "owner_id": 8,
            "hull_id": 92,
            "first_turn": 9,
            "last_turn": 10,
            "points": [
                {
                    "turn": 9,
                    "gap_from_previous": False,
                    "evidence": "combat",
                    "combat_outcome": "unknown",
                    "post_host_confirmed": False,
                    "combat_event": {
                        "sides": [
                            {
                                "object_kind": "ship",
                                "object_id": 20,
                                "name": "OLD HULL",
                                "owner_id": 4,
                                "hull_id": 70,
                            }
                        ],
                    },
                },
                {
                    "turn": 10,
                    "gap_from_previous": False,
                    "evidence": "scan",
                    "combat_outcome": None,
                    "post_host_confirmed": False,
                    "combat_event": None,
                },
            ],
        }

        segments = _segment_track(track)

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["hull_id"], 70)
        self.assertEqual(segments[1]["hull_id"], 92)

    def test_defeated_same_hull_is_not_proof_of_new_identity(self):
        track = {
            "ship_id": 44,
            "name": "CAPTURE-COMPATIBLE SHIP",
            "owner_id": 8,
            "hull_id": 70,
            "first_turn": 9,
            "last_turn": 10,
            "points": [
                {
                    "turn": 9,
                    "gap_from_previous": False,
                    "evidence": "combat",
                    "combat_outcome": "defeated",
                    "post_host_confirmed": False,
                    "combat_event": {
                        "sides": [
                            {
                                "object_kind": "ship",
                                "object_id": 44,
                                "name": "CAPTURE-COMPATIBLE SHIP",
                                "owner_id": 4,
                                "hull_id": 70,
                            }
                        ],
                    },
                },
                {
                    "turn": 10,
                    "gap_from_previous": False,
                    "evidence": "scan",
                    "combat_outcome": None,
                    "post_host_confirmed": False,
                    "combat_event": None,
                },
            ],
        }

        segments = _segment_track(track)

        self.assertEqual(len(segments), 1)
        self.assertEqual(len(segments[0]["points"]), 2)


if __name__ == "__main__":
    unittest.main()
