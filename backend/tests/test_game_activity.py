import unittest

from app.services.game_activity import flatten_activity_records


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


if __name__ == "__main__":
    unittest.main()
