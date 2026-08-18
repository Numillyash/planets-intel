import unittest

from app.api.routes.games import _optional_nonnegative_int, build_player_info


BASE_PLAYER = {
    "id": 2,
    "accountid": 123,
    "username": "Example",
    "raceid": 2,
    "status": 1,
    "turnstatus": 1,
    "planets": 10,
    "ships": 7,
    "starbases": 1,
    "turnready": False,
}


class GamePlayerMissedTurnsTests(unittest.TestCase):
    def test_live_turnsmissed_is_exposed_as_consecutive_streak(self) -> None:
        player = build_player_info({**BASE_PLAYER, "turnsmissed": 2})
        self.assertEqual(player.turns_missed, 2)

    def test_missing_turnsmissed_stays_unknown(self) -> None:
        player = build_player_info(BASE_PLAYER)
        self.assertIsNone(player.turns_missed)

    def test_invalid_values_fail_closed_to_unknown(self) -> None:
        for value in (True, False, -1, "2", 2.0, None):
            with self.subTest(value=value):
                self.assertIsNone(_optional_nonnegative_int(value))

    def test_zero_is_preserved_as_known_zero(self) -> None:
        self.assertEqual(_optional_nonnegative_int(0), 0)


if __name__ == "__main__":
    unittest.main()
