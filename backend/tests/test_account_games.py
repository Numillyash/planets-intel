import unittest

from app.services.account_games import _game_record_from_remote


class AccountGameRecordTests(unittest.TestCase):
    def test_remote_record_preserves_compact_turn_status(self):
        raw = {
            "id": 123,
            "name": "Example",
            "shortdescription": "Standard",
            "status": 2,
            "statusname": "Running",
            "turn": 17,
            "slots": 5,
            "turnstatus": "_o3xc",
            "nexthost": "",
            "timetohost": "Next turn in 1 hour",
            "isprivate": False,
            "iscustom": False,
        }

        record = _game_record_from_remote(raw)

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["turn_status"], "_o3xc")
        self.assertEqual(record["slots"], 5)

    def test_missing_or_invalid_turn_status_stays_unknown(self):
        base = {
            "id": 123,
            "name": "Example",
            "status": 2,
            "statusname": "Running",
            "turn": 17,
            "slots": 5,
        }

        missing = _game_record_from_remote(base)
        invalid = _game_record_from_remote({**base, "turnstatus": ["_"]})

        self.assertIsNotNone(missing)
        self.assertIsNotNone(invalid)
        assert missing is not None and invalid is not None
        self.assertIsNone(missing["turn_status"])
        self.assertIsNone(invalid["turn_status"])


if __name__ == "__main__":
    unittest.main()
