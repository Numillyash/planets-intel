import unittest

from app.services.private_messages import _message_key


class PrivateMessageIdentityTests(unittest.TestCase):
    def test_message_id_is_stable_within_source_collection(self) -> None:
        first = {
            "id": 464,
            "headline": "Long Range Sensors",
            "body": "first body",
        }
        changed = {
            "id": 464,
            "headline": "Long Range Sensors",
            "body": "changed body",
        }

        self.assertEqual(
            _message_key("messages", first),
            _message_key("messages", changed),
        )

    def test_same_upstream_id_in_different_collections_stays_distinct(self) -> None:
        raw = {"id": 464}

        self.assertNotEqual(
            _message_key("messages", raw),
            _message_key("mymessages", raw),
        )

    def test_idless_message_identity_uses_raw_semantic_fields(self) -> None:
        base = {
            "messagetype": 7,
            "turn": 8,
            "ownerid": 2,
            "target": 7,
            "headline": "Message",
            "body": "Hello",
            "x": 0,
            "y": 0,
        }
        changed = {**base, "body": "Different"}

        self.assertNotEqual(
            _message_key("messages", base),
            _message_key("messages", changed),
        )


if __name__ == "__main__":
    unittest.main()
