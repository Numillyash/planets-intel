import unittest
from types import SimpleNamespace

from app.services.spatial_messages import _collapse_spatial_messages


class SpatialMessagePresentationTests(unittest.TestCase):
    def test_same_message_from_multiple_collections_collapses(self) -> None:
        common = {
            "message_id": 464,
            "message_type": 10,
            "message_turn": 8,
            "owner_id": 7,
            "target_id": 0,
            "headline": "Long Range Sensors",
            "body": "Distress call and explosion detected at (1684, 1796)",
            "x": 1684,
            "y": 1796,
        }
        rows = [
            SimpleNamespace(source_collection="messages", **common),
            SimpleNamespace(source_collection="mymessages", **common),
        ]

        result = _collapse_spatial_messages(
            rows,
            batch_id=123,
            observed_at="2026-09-28T00:00:00Z",
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]["source_collections"],
            ["messages", "mymessages"],
        )

    def test_semantically_distinct_messages_at_same_position_stay_distinct(self) -> None:
        first = SimpleNamespace(
            source_collection="messages",
            message_id=1,
            message_type=10,
            message_turn=8,
            owner_id=7,
            target_id=0,
            headline="Long Range Sensors",
            body="First",
            x=1684,
            y=1796,
        )
        second = SimpleNamespace(
            source_collection="messages",
            message_id=2,
            message_type=10,
            message_turn=8,
            owner_id=7,
            target_id=0,
            headline="Long Range Sensors",
            body="Second",
            x=1684,
            y=1796,
        )

        result = _collapse_spatial_messages(
            [first, second],
            batch_id=123,
            observed_at=None,
        )

        self.assertEqual(len(result), 2)
        self.assertNotEqual(result[0]["message_key"], result[1]["message_key"])


if __name__ == "__main__":
    unittest.main()
