import unittest

from app.services.private_sync import (
    _is_unknown_player_sentinel,
    _payload_with_resolved_player_slot,
)


class PrivateSyncIdentityTests(unittest.TestCase):
    def test_recognizes_exact_unknown_player_sentinel(self) -> None:
        self.assertTrue(
            _is_unknown_player_sentinel(
                {
                    "id": 0,
                    "accountid": 0,
                    "username": "unknown",
                    "raceid": 0,
                    "status": 0,
                }
            )
        )

    def test_does_not_treat_partial_identity_as_sentinel(self) -> None:
        self.assertFalse(
            _is_unknown_player_sentinel(
                {"id": 0, "accountid": 33734, "username": "unknown"}
            )
        )
        self.assertFalse(
            _is_unknown_player_sentinel(
                {"id": 3, "accountid": 0, "username": "unknown"}
            )
        )
        self.assertFalse(
            _is_unknown_player_sentinel(
                {"id": 0, "accountid": 0, "username": "georgul"}
            )
        )

    def test_persistence_view_only_replaces_batch_source_slot(self) -> None:
        payload = {
            "rst": {
                "player": {
                    "id": 0,
                    "accountid": 0,
                    "username": "unknown",
                    "raceid": 0,
                },
                "ships": [{"id": 12, "name": "Observed"}],
            }
        }

        normalized = _payload_with_resolved_player_slot(payload, player_slot_id=3)

        self.assertEqual(normalized["rst"]["player"]["id"], 3)
        self.assertEqual(normalized["rst"]["player"]["accountid"], 0)
        self.assertEqual(normalized["rst"]["player"]["username"], "unknown")
        self.assertEqual(normalized["rst"]["ships"], payload["rst"]["ships"])
        self.assertEqual(payload["rst"]["player"]["id"], 0)


if __name__ == "__main__":
    unittest.main()
