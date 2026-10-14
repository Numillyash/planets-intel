import unittest
from unittest.mock import AsyncMock

from app.planetsnu.client import PlanetsNuClient


class PlanetsNuSendMessageTests(unittest.IsolatedAsyncioTestCase):
    def make_client(self) -> PlanetsNuClient:
        client = PlanetsNuClient.__new__(PlanetsNuClient)
        client.post_form = AsyncMock(return_value={"success": True, "html": "ok"})
        return client

    async def test_public_board_omits_to_field_entirely(self):
        client = self.make_client()

        await client.send_message(
            game_id=683545,
            player_id=3,
            api_key="secret",
            recipient_player_ids=[],
            body="Do you know any guides to birdman?",
        )

        kwargs = client.post_form.await_args.kwargs
        self.assertNotIn("to", kwargs["data"])
        self.assertEqual(
            kwargs["data"],
            {
                "gameid": 683545,
                "playerid": 3,
                "apikey": "secret",
                "body": "Do you know any guides to birdman?",
            },
        )
        self.assertFalse(kwargs["allow_proxy_fallback"])
        self.assertTrue(kwargs["ambiguous_write"])

    async def test_private_message_includes_comma_separated_to_field(self):
        client = self.make_client()

        await client.send_message(
            game_id=123,
            player_id=3,
            api_key="secret",
            recipient_player_ids=[5, 7],
            body="alpha & beta = gamma",
        )

        kwargs = client.post_form.await_args.kwargs
        self.assertEqual(kwargs["data"]["to"], "5,7")
        self.assertEqual(kwargs["data"]["body"], "alpha ||| beta ::: gamma")


if __name__ == "__main__":
    unittest.main()
