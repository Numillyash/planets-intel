import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.services.public_archive_turn import (
    ArchiveNotPublicOrFinished,
    ArchiveSourceMismatch,
    adapt_finished_public_turn,
    assert_finished_public_game,
    fetch_finished_public_turn,
)


GAME_ID = 123001


def finished_info():
    return {
        "game": {"id": GAME_ID, "status": 3, "isprivate": False, "turn": 40},
        "players": [{"id": 4, "username": "Archival Pilot", "raceid": 4}],
    }


def historical_payload():
    return {
        "success": True,
        "savekey": "DO_NOT_EXPOSE",
        "rst": {
            "game": {"id": GAME_ID, "turn": 17},
            "player": {"id": 4, "apikey": "SECRET"},
            "planets": [{
                "id": 12, "ownerid": 4, "x": 125, "y": 220,
                "name": "Alpha", "infoturn": 17, "savekey": "SECRET",
                "clans": 100,
            }],
            "ships": [{
                "id": 9, "ownerid": 4, "x": 125, "y": 220,
                "hullid": 15, "warp": 7, "name": "Archive Ship",
            }],
            "starbases": [],
        },
    }


class PublicArchiveTurnTests(unittest.TestCase):
    def test_strictly_finished_public_identity(self):
        assert_finished_public_game(finished_info(), GAME_ID)
        for game in (
            {"id": GAME_ID, "status": 2, "isprivate": False},
            {"id": GAME_ID, "status": 3, "isprivate": True},
            {"id": GAME_ID, "status": 3},
            {"id": GAME_ID + 1, "status": 3, "isprivate": False},
        ):
            with self.subTest(game=game), self.assertRaises(ArchiveNotPublicOrFinished):
                assert_finished_public_game(
                    {"game": game, "players": [{"id": 4}]}, GAME_ID
                )

    def test_archive_entities_reuse_readonly_fact_shapes(self):
        result = adapt_finished_public_turn(
            info=finished_info(), payload=historical_payload(),
            game_id=GAME_ID, player_id=4, turn=17,
        )
        self.assertEqual(result["mode"], "public_finished_archive")
        self.assertEqual(result["player_slot_id"], 4)
        self.assertEqual(result["planets"][0]["name"], "Alpha")
        self.assertEqual(result["ships"][0]["ship_id"], 9)
        self.assertNotIn("savekey", result["planets"][0]["payload"])
        self.assertNotIn("apikey", str(result).lower())
        self.assertNotIn("SECRET", str(result))

    def test_reject_wrong_result_game_turn_or_player(self):
        for key, field, changed in (
            ("game", "id", GAME_ID + 1),
            ("game", "turn", 18),
            ("player", "id", 5),
        ):
            payload = historical_payload()
            payload["rst"][key][field] = changed
            with self.subTest(key=key, field=field), self.assertRaises(ArchiveSourceMismatch):
                adapt_finished_public_turn(
                    info=finished_info(), payload=payload,
                    game_id=GAME_ID, player_id=4, turn=17,
                )

    def test_reject_unknown_slot_and_missing_rst_arrays(self):
        with self.assertRaises(ArchiveSourceMismatch):
            adapt_finished_public_turn(
                info=finished_info(), payload=historical_payload(),
                game_id=GAME_ID, player_id=5, turn=17,
            )
        payload = historical_payload()
        del payload["rst"]["planets"]
        with self.assertRaises(ArchiveSourceMismatch):
            adapt_finished_public_turn(
                info=finished_info(), payload=payload,
                game_id=GAME_ID, player_id=4, turn=17,
            )

    def test_active_game_never_calls_loadturn(self):
        info = finished_info()
        info["game"]["status"] = 2
        client = AsyncMock()
        client.load_info.return_value = info
        with patch(
            "app.services.public_archive_turn.PlanetsNuClient",
            return_value=client,
        ):
            with self.assertRaises(ArchiveNotPublicOrFinished):
                asyncio.run(fetch_finished_public_turn(GAME_ID, 4, 17))
        client.load_finished_public_turn.assert_not_awaited()

    def test_completed_game_calls_only_credential_free_method(self):
        client = AsyncMock()
        client.load_info.return_value = finished_info()
        client.load_finished_public_turn.return_value = historical_payload()
        with patch(
            "app.services.public_archive_turn.PlanetsNuClient",
            return_value=client,
        ):
            data = asyncio.run(fetch_finished_public_turn(GAME_ID, 4, 17))
        self.assertEqual(data["turn"], 17)
        client.load_finished_public_turn.assert_awaited_once_with(
            game_id=GAME_ID, player_id=4, turn=17,
        )
        client.load_turn.assert_not_awaited()

    def test_archive_transport_cannot_send_api_key_or_save_capability(self):
        from app.planetsnu.client import PlanetsNuClient

        client = object.__new__(PlanetsNuClient)
        request = AsyncMock(return_value=historical_payload())
        client.post_form = request
        result = asyncio.run(client.load_finished_public_turn(
            game_id=GAME_ID, player_id=4, turn=17,
        ))
        self.assertIn("rst", result)
        request.assert_awaited_once()
        args, kwargs = request.await_args
        self.assertEqual(args[0], "game/loadturn")
        data = args[1]
        self.assertEqual(data["gameid"], GAME_ID)
        self.assertEqual(data["playerid"], 4)
        self.assertEqual(data["turn"], 17)
        self.assertEqual(data["forsave"], "false")
        self.assertNotIn("apikey", data)
        self.assertNotIn("savekey", data)
