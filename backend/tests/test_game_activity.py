import unittest

from app.models.game_activity_observation import GameActivityObservation
from app.services.game_activity import _activity_semantics, flatten_activity_records


class GameActivityFlattenTests(unittest.TestCase):
    def test_flattens_nested_replies_and_deduplicates_ids(self) -> None:
        records = [
            {
                "id": 100,
                "message": "root",
                "_replies": [
                    {
                        "id": 101,
                        "message": "reply",
                        "_replies": [
                            {"id": 102, "message": "nested"},
                        ],
                    },
                    {"id": 101, "message": "duplicate reply"},
                ],
            }
        ]

        flattened = flatten_activity_records(records)
        self.assertEqual([item["id"] for item in flattened], [100, 101, 102])

    def test_skips_records_without_positive_activity_id(self) -> None:
        records = [
            {"id": 0, "message": "zero"},
            {"id": -1, "message": "negative"},
            {"message": "missing"},
            {"id": 7, "message": "valid"},
        ]

        self.assertEqual(
            [item["id"] for item in flatten_activity_records(records)],
            [7],
        )


class GameActivitySemanticTests(unittest.TestCase):
    def test_direct_thread_reply_inherits_private_partner(self) -> None:
        root = GameActivityObservation(
            activity_id=100,
            activity_type=1,
            scope=3,
            parent_id=0,
            source_id=33734,
            source_name="observer",
            target_id=90192,
            target_name="other player",
            target_type=1,
        )
        reply = GameActivityObservation(
            activity_id=101,
            activity_type=1,
            scope=3,
            parent_id=100,
            source_id=90192,
            source_name="other player",
            target_id=0,
            target_name=None,
            target_type=0,
        )
        rows_by_id = {100: root, 101: reply}

        root_semantics = _activity_semantics(
            root,
            rows_by_id=rows_by_id,
            observer_account_id=33734,
        )
        reply_semantics = _activity_semantics(
            reply,
            rows_by_id=rows_by_id,
            observer_account_id=33734,
        )

        self.assertEqual(root_semantics["kind"], "private_message")
        self.assertEqual(reply_semantics["kind"], "private_message")
        self.assertEqual(reply_semantics["thread_root_id"], 100)
        self.assertEqual(reply_semantics["conversation_with_id"], 90192)
        self.assertEqual(reply_semantics["conversation_with_name"], "other player")

    def test_unproven_player_visibility_stays_unclassified(self) -> None:
        row = GameActivityObservation(
            activity_id=200,
            activity_type=1,
            scope=2,
            parent_id=0,
            source_id=1,
            target_id=0,
            target_type=0,
        )
        semantics = _activity_semantics(
            row,
            rows_by_id={200: row},
            observer_account_id=33734,
        )
        self.assertEqual(semantics["kind"], "player_message")
        self.assertIsNone(semantics["conversation_with_id"])


if __name__ == "__main__":
    unittest.main()
