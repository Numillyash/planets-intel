import unittest

from app.scripts.inspect_account_games import (
    _interesting_player_fields,
    _marker,
)


class InspectAccountGamesTests(unittest.TestCase):
    def test_marker_is_slot_ordered_and_bounds_checked(self) -> None:
        self.assertEqual(_marker("_o3xc", 1), "_")
        self.assertEqual(_marker("_o3xc", 2), "o")
        self.assertEqual(_marker("_o3xc", 5), "c")
        self.assertIsNone(_marker("_o3xc", 0))
        self.assertIsNone(_marker("_o3xc", 6))
        self.assertIsNone(_marker(None, 1))

    def test_interesting_fields_keep_turn_and_drop_diagnostics_only(self) -> None:
        player = {
            "id": 2,
            "username": "Example",
            "turnready": False,
            "turnstatus": 1,
            "status": 1,
            "missedturns": 2,
            "dropped": False,
            "planets": 15,
        }

        result = _interesting_player_fields(player)

        self.assertEqual(
            result,
            {
                "dropped": False,
                "missedturns": 2,
                "status": 1,
                "turnready": False,
                "turnstatus": 1,
            },
        )
        self.assertNotIn("planets", result)
        self.assertNotIn("username", result)


if __name__ == "__main__":
    unittest.main()
