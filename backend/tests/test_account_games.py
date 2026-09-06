import unittest
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app.services.account_games import (
    _cached_membership_condition,
    _game_record_from_cache,
    _game_record_from_remote,
    _merge_remote_observer_evidence,
)


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

    def test_sentinel_account_id_cannot_match_cached_sentinel_slots(self):
        account = SimpleNamespace(
            planets_account_id=0,
            planets_username="  GeOrGuL  ",
        )

        sql = str(
            _cached_membership_condition(account).compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertNotIn("account_id = 0", sql)
        self.assertIn("lower(trim(game_player_slots.username)) = 'georgul'", sql)

    def test_positive_account_id_and_username_are_both_membership_evidence(self):
        account = SimpleNamespace(
            planets_account_id=33734,
            planets_username="georgul",
        )

        sql = str(
            _cached_membership_condition(account).compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

        self.assertIn("game_player_slots.account_id = 33734", sql)
        self.assertIn("lower(trim(game_player_slots.username)) = 'georgul'", sql)
        self.assertIn(" OR ", sql)

    def test_no_usable_cached_identity_matches_nothing(self):
        account = SimpleNamespace(
            planets_account_id=None,
            planets_username="   ",
        )
        self.assertIs(_cached_membership_condition(account), False)

    def test_cached_record_carries_historical_observer_status(self):
        game = SimpleNamespace(
            id=684000,
            name="Bernices Sector",
            status_id=2,
            status_name="Running",
            current_turn=42,
            slots=8,
            is_private=False,
            is_custom=False,
        )

        record = _game_record_from_cache(
            game,
            observer_slot_id=4,
            observer_status=0,
            membership_source="historical-private-observation",
        )

        self.assertEqual(record["observer_slot_id"], 4)
        self.assertEqual(record["observer_status"], 0)
        self.assertEqual(
            record["membership_source"],
            "historical-private-observation",
        )

    def test_remote_metadata_preserves_cached_observer_evidence(self):
        remote = _game_record_from_remote(
            {
                "id": 684000,
                "name": "Bernices Sector",
                "status": 2,
                "statusname": "Running",
                "turn": 43,
                "slots": 8,
            }
        )
        self.assertIsNotNone(remote)
        assert remote is not None

        cached = {
            **remote,
            "turn": 42,
            "data_source": "canonical-cache",
            "observer_slot_id": 4,
            "observer_status": 0,
            "membership_source": "historical-private-observation",
        }
        merged = _merge_remote_observer_evidence(remote, cached)

        self.assertEqual(merged["turn"], 43)
        self.assertEqual(merged["data_source"], "planets.nu")
        self.assertEqual(merged["observer_slot_id"], 4)
        self.assertEqual(merged["observer_status"], 0)
        self.assertEqual(
            merged["membership_source"],
            "historical-private-observation",
        )


if __name__ == "__main__":
    unittest.main()
