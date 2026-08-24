import unittest
from unittest.mock import AsyncMock, patch

from app.planetsnu.client import PlanetsNuClient
from app.services.communication_write import (
    CommunicationWriteError,
    _reconciled_activity_id,
    _resolve_reply_parent,
    send_owned_game_message,
)


PRIVATE_ROOT = {
    "activity_id": 100,
    "parent_id": 0,
    "thread_root_id": 100,
    "kind": "private_message",
    "conversation_player_ids": [2, 5],
    "source_id": 901,
    "message": "root",
}
PRIVATE_CHILD = {
    "activity_id": 101,
    "parent_id": 100,
    "thread_root_id": 100,
    "kind": "private_message",
    "conversation_player_ids": [2, 5],
    "source_id": 905,
    "message": "child",
}


class CommunicationReplyPureTests(unittest.TestCase):
    def test_private_root_reply_resolves_root(self):
        self.assertEqual(
            _resolve_reply_parent(
                activity={"items": [PRIVATE_ROOT, PRIVATE_CHILD]},
                reply_to_activity_id=100,
                recipient_player_ids=[2, 5],
            ),
            100,
        )

    def test_reply_to_child_normalizes_to_thread_root(self):
        self.assertEqual(
            _resolve_reply_parent(
                activity={"items": [PRIVATE_ROOT, PRIVATE_CHILD]},
                reply_to_activity_id=101,
                recipient_player_ids=[5, 2],
            ),
            100,
        )

    def test_private_reply_rejects_changed_recipient_set(self):
        with self.assertRaisesRegex(
            CommunicationWriteError,
            "do not match the factual thread participants",
        ):
            _resolve_reply_parent(
                activity={"items": [PRIVATE_ROOT, PRIVATE_CHILD]},
                reply_to_activity_id=101,
                recipient_player_ids=[2],
            )

    def test_public_reply_requires_zero_private_recipients(self):
        public_root = {
            "activity_id": 200,
            "parent_id": 0,
            "thread_root_id": 200,
            "kind": "player_message",
            "conversation_player_ids": [],
        }
        self.assertEqual(
            _resolve_reply_parent(
                activity={"items": [public_root]},
                reply_to_activity_id=200,
                recipient_player_ids=[],
            ),
            200,
        )
        with self.assertRaisesRegex(
            CommunicationWriteError,
            "cannot include private recipients",
        ):
            _resolve_reply_parent(
                activity={"items": [public_root]},
                reply_to_activity_id=200,
                recipient_player_ids=[2],
            )

    def test_reply_reconciliation_requires_exact_parent(self):
        activity = {
            "items": [
                {
                    "activity_id": 300,
                    "source_id": 900,
                    "target_id": 901,
                    "message": "same text",
                    "parent_id": 0,
                },
                {
                    "activity_id": 301,
                    "source_id": 900,
                    "target_id": None,
                    "message": "same text",
                    "parent_id": 100,
                },
            ]
        }
        self.assertEqual(
            _reconciled_activity_id(
                activity=activity,
                previous_activity_ids=set(),
                sender_planets_account_id=900,
                recipient_account_ids={2: 901, 5: 905},
                body="same text",
                game_id=123,
                expected_parent_id=100,
            ),
            301,
        )

    def test_root_reconciliation_rejects_child_with_same_text(self):
        activity = {
            "items": [
                {
                    "activity_id": 301,
                    "source_id": 900,
                    "target_id": None,
                    "message": "same text",
                    "parent_id": 100,
                }
            ]
        }
        self.assertIsNone(
            _reconciled_activity_id(
                activity=activity,
                previous_activity_ids=set(),
                sender_planets_account_id=900,
                recipient_account_ids={2: 901},
                body="same text",
                game_id=123,
            )
        )


class PlanetsNuReplyWireTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_message_serializes_parentid_exactly(self):
        client = object.__new__(PlanetsNuClient)
        client.post_form = AsyncMock(return_value={"success": True})

        await client.send_message(
            game_id=123,
            player_id=4,
            api_key="secret",
            recipient_player_ids=[2, 5],
            body="reply",
            parent_id=100,
        )

        call = client.post_form.await_args
        self.assertEqual(call.args[0], "game/sendmessage")
        self.assertEqual(call.kwargs["data"]["parentid"], 100)
        self.assertEqual(call.kwargs["data"]["to"], "2,5")

    async def test_root_send_omits_parentid(self):
        client = object.__new__(PlanetsNuClient)
        client.post_form = AsyncMock(return_value={"success": True})

        await client.send_message(
            game_id=123,
            player_id=4,
            api_key="secret",
            recipient_player_ids=[],
            body="root",
        )

        data = client.post_form.await_args.kwargs["data"]
        self.assertNotIn("parentid", data)
        self.assertNotIn("to", data)


class _FakePlanetsClient:
    current_payload = {
        "success": True,
        "canmessage": True,
        "rst": {
            "player": {
                "id": 4,
                "accountid": 900,
                "username": "observer",
            }
        },
    }
    send_calls = []

    async def load_turn(self, *, game_id, api_key):
        return self.__class__.current_payload

    async def send_message(self, **kwargs):
        self.__class__.send_calls.append(kwargs)
        return {"success": True, "html": "sent"}


class CommunicationReplyWriteTests(unittest.IsolatedAsyncioTestCase):
    async def test_reply_to_reply_sends_root_parent_and_reconciles_child(self):
        _FakePlanetsClient.send_calls = []
        before = {"items": [PRIVATE_ROOT, PRIVATE_CHILD]}
        after = {
            "items": [
                PRIVATE_ROOT,
                PRIVATE_CHILD,
                {
                    "activity_id": 102,
                    "parent_id": 100,
                    "thread_root_id": 100,
                    "kind": "private_message",
                    "conversation_player_ids": [2, 5],
                    "source_id": 900,
                    "target_id": None,
                    "message": "Test3 fixed",
                },
            ]
        }

        with (
            patch(
                "app.services.communication_write._load_owned_account",
                return_value={
                    "id": 1,
                    "username": "observer",
                    "planets_account_id": 900,
                    "api_key_encrypted": "encrypted",
                },
            ),
            patch(
                "app.services.communication_write.decrypt_credential",
                return_value="secret",
            ),
            patch(
                "app.services.communication_write.PlanetsNuClient",
                _FakePlanetsClient,
            ),
            patch(
                "app.services.communication_write._validate_sender",
                return_value=(4, 900),
            ),
            patch(
                "app.services.communication_write._validate_recipients",
                return_value=([2, 5], {2: 901, 5: 905}),
            ),
            patch(
                "app.services.communication_write.get_owned_game_activity",
                side_effect=[before, after],
            ),
            patch(
                "app.services.communication_write.sync_private_game",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "app.services.communication_write.mark_outgoing_private_message",
                return_value=True,
            ) as mark_message,
        ):
            result = await send_owned_game_message(
                user_id=7,
                linked_account_id=1,
                game_id=123,
                recipient_player_ids=[2, 5],
                body="Test3 fixed",
                reply_to_activity_id=101,
            )

        self.assertEqual(_FakePlanetsClient.send_calls[0]["parent_id"], 100)
        self.assertEqual(result["parent_activity_id"], 100)
        self.assertTrue(result["reconciled"])
        mark_message.assert_called_once_with(
            linked_account_id=1,
            game_id=123,
            activity_id=102,
            recipient_player_ids=[2, 5],
        )


if __name__ == "__main__":
    unittest.main()
