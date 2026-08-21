import unittest
from unittest.mock import AsyncMock, patch

from app.services.communication_write import (
    CommunicationWriteAmbiguousError,
    _activity_ids,
    _message_key,
    _reconciled_message,
    send_owned_game_message,
)
from app.planetsnu.client import PlanetsNuAmbiguousWriteError


class _FakePlanetsClient:
    current_payload = None
    send_payload = {"success": True, "html": "sent"}
    send_calls = []
    send_error = None

    async def load_turn(self, *, game_id, api_key):
        return self.__class__.current_payload

    async def send_message(self, **kwargs):
        self.__class__.send_calls.append(kwargs)
        if self.__class__.send_error is not None:
            raise self.__class__.send_error
        return self.__class__.send_payload


class CommunicationWritePureTests(unittest.TestCase):
    def test_message_key_normalizes_planets_html_breaks(self):
        self.assertEqual(_message_key("alpha<br>beta &amp; gamma"), "alpha\nbeta & gamma")

    def test_activity_ids_ignores_malformed_items(self):
        self.assertEqual(
            _activity_ids({"items": [{"activity_id": 2}, {"activity_id": True}, None]}),
            {2},
        )

    def test_reconciliation_requires_new_outgoing_message(self):
        activity = {
            "items": [
                {
                    "activity_id": 10,
                    "source_id": 900,
                    "target_id": 901,
                    "message": "hello<br>there",
                },
                {
                    "activity_id": 11,
                    "source_id": 900,
                    "target_id": 901,
                    "message": "hello<br>there",
                },
            ]
        }
        self.assertTrue(
            _reconciled_message(
                activity=activity,
                previous_activity_ids={10},
                sender_planets_account_id=900,
                recipient_account_ids={2: 901},
                body="hello\nthere",
            )
        )
        self.assertFalse(
            _reconciled_message(
                activity=activity,
                previous_activity_ids={10, 11},
                sender_planets_account_id=900,
                recipient_account_ids={2: 901},
                body="hello\nthere",
            )
        )


class CommunicationWriteAsyncTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _FakePlanetsClient.current_payload = {
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
        _FakePlanetsClient.send_payload = {"success": True, "html": "sent"}
        _FakePlanetsClient.send_calls = []
        _FakePlanetsClient.send_error = None

    async def test_success_is_distinct_from_reconciliation(self):
        before = {"items": [{"activity_id": 10}]}
        after = {
            "items": [
                {"activity_id": 10},
                {
                    "activity_id": 11,
                    "source_id": 900,
                    "target_id": 901,
                    "message": "hello",
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
                return_value=([2], {2: 901}),
            ),
            patch(
                "app.services.communication_write.get_owned_game_activity",
                side_effect=[before, after],
            ),
            patch(
                "app.services.communication_write.sync_private_game",
                new=AsyncMock(return_value={}),
            ),
        ):
            result = await send_owned_game_message(
                user_id=7,
                linked_account_id=1,
                game_id=123,
                recipient_player_ids=[2],
                body="hello",
            )

        self.assertTrue(result["upstream_accepted"])
        self.assertTrue(result["reconciled"])
        self.assertEqual(len(_FakePlanetsClient.send_calls), 1)

    async def test_ambiguous_write_is_never_reported_as_success(self):
        _FakePlanetsClient.send_error = PlanetsNuAmbiguousWriteError("lost response")
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
                return_value=([2], {2: 901}),
            ),
            patch(
                "app.services.communication_write.get_owned_game_activity",
                return_value={"items": []},
            ),
        ):
            with self.assertRaisesRegex(
                CommunicationWriteAmbiguousError,
                "did not retry",
            ):
                await send_owned_game_message(
                    user_id=7,
                    linked_account_id=1,
                    game_id=123,
                    recipient_player_ids=[2],
                    body="hello",
                )

        self.assertEqual(len(_FakePlanetsClient.send_calls), 1)


if __name__ == "__main__":
    unittest.main()
