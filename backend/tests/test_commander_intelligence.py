import unittest

from app.services.commander_intelligence import (
    canonical_username,
    exact_overlap_intervals,
    reconstruct_participation_intervals,
    public_roster_from_loadinfo,
)


def event(
    *,
    event_id: int,
    event_type: int,
    turn: int,
    player_id: int,
    description: str,
) -> dict:
    return {
        "id": event_id,
        "eventtype": event_type,
        "turn": turn,
        "playerid": player_id,
        "description": description,
    }


class CommanderParticipationTests(unittest.TestCase):
    def test_username_canonicalization_is_case_and_space_insensitive(self) -> None:
        self.assertEqual(
            canonical_username("  Example   Commander "),
            "example commander",
        )

    def test_multiple_join_drop_periods_are_preserved(self) -> None:
        payload = {
            "game": {"id": 700001, "turn": 50},
            "players": [
                {
                    "id": 4,
                    "username": "Example",
                    "raceid": 2,
                    "status": 1,
                    "turnjoined": 20,
                    "statusturn": 0,
                }
            ],
            "events": [
                event(
                    event_id=101,
                    event_type=3,
                    turn=2,
                    player_id=4,
                    description=(
                        "Example has joined the game in slot 4 "
                        "as Lizard Alliance"
                    ),
                ),
                event(
                    event_id=102,
                    event_type=10,
                    turn=10,
                    player_id=4,
                    description="Example has been dropped from the game",
                ),
                event(
                    event_id=103,
                    event_type=3,
                    turn=20,
                    player_id=4,
                    description=(
                        "Example has joined the game in slot 4 "
                        "as Lizard Alliance"
                    ),
                ),
            ],
        }

        result = reconstruct_participation_intervals(payload, "example")

        self.assertEqual(len(result), 2)
        self.assertEqual(
            (result[0]["turn_from"], result[0]["turn_to"]),
            (2, 10),
        )
        self.assertEqual(result[0]["reconstruction_quality"], "event_bounded")
        self.assertEqual(result[0]["source_event_ids"], [101, 102])
        self.assertTrue(result[0]["bounds_known"])

        self.assertEqual(
            (result[1]["turn_from"], result[1]["turn_to"]),
            (20, 50),
        )
        self.assertEqual(
            result[1]["reconstruction_quality"],
            "event_open_roster",
        )
        self.assertEqual(result[1]["source_event_ids"], [103])
        self.assertTrue(result[1]["bounds_known"])

    def test_drop_without_join_keeps_start_unknown(self) -> None:
        payload = {
            "game": {"id": 700002, "turn": 30},
            "players": [{"id": 5, "username": "dead", "raceid": 3, "status": 2}],
            "events": [
                event(
                    event_id=201,
                    event_type=10,
                    turn=12,
                    player_id=5,
                    description="Former Pilot has been dropped from the game",
                )
            ],
        }

        result = reconstruct_participation_intervals(
            payload,
            "Former Pilot",
        )

        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["turn_from"])
        self.assertEqual(result[0]["turn_to"], 12)
        self.assertFalse(result[0]["bounds_known"])
        self.assertEqual(
            result[0]["reconstruction_quality"],
            "event_start_unknown",
        )

    def test_roster_fallback_uses_turnjoined_and_statusturn(self) -> None:
        payload = {
            "game": {"id": 700003, "turn": 30},
            "players": [
                {
                    "id": 6,
                    "username": "Retired",
                    "raceid": 8,
                    "status": 2,
                    "turnjoined": 3,
                    "statusturn": 17,
                }
            ],
            "events": [],
        }

        result = reconstruct_participation_intervals(payload, "Retired")

        self.assertEqual(len(result), 1)
        self.assertEqual(
            (result[0]["turn_from"], result[0]["turn_to"]),
            (3, 17),
        )
        self.assertEqual(
            result[0]["reconstruction_quality"],
            "roster_fallback",
        )
        self.assertTrue(result[0]["bounds_known"])

    def test_exact_overlap_preserves_disjoint_intervals_without_double_counting(self) -> None:
        left = [
            {"turn_from": 2, "turn_to": 10},
            {"turn_from": 20, "turn_to": 30},
        ]
        right = [
            {"turn_from": 5, "turn_to": 7},
            {"turn_from": 25, "turn_to": 35},
        ]

        self.assertEqual(
            exact_overlap_intervals(left, right),
            [
                {"turn_from": 5, "turn_to": 7, "turn_count": 3},
                {"turn_from": 25, "turn_to": 30, "turn_count": 6},
            ],
        )

    def test_unknown_bound_never_creates_false_exact_overlap(self) -> None:
        left = [{"turn_from": None, "turn_to": 12}]
        right = [{"turn_from": 1, "turn_to": 20}]

        self.assertEqual(exact_overlap_intervals(left, right), [])


if __name__ == "__main__":
    unittest.main()


class PublicSectorRosterTests(unittest.TestCase):
    def test_current_public_participants_without_linked_game(self) -> None:
        payload = {
            "game": {
                "id": 99911, "name": "Another Sector", "turn": 42,
                "status": 2, "statusname": "Running", "isprivate": False,
            },
            "players": [
                {"id": 1, "username": "Alpha", "raceid": 1, "status": 1,
                 "accountid": 515},
                {"id": 2, "username": "Beta", "raceid": 5, "status": 1},
                {"id": 3, "username": "dead", "raceid": 6, "status": 2},
                {"id": 4, "username": "computer", "raceid": 100, "status": 1},
            ],
        }
        result = public_roster_from_loadinfo(payload, 99911)
        self.assertIsNotNone(result)
        game, players = result
        self.assertEqual(game["game_name"], "Another Sector")
        self.assertEqual(game["turn"], 42)
        self.assertEqual([p["username"] for p in players], ["Alpha", "Beta"])
        self.assertEqual(players[0]["account_id"], 515)
        self.assertEqual(players[0]["source"], "planets.nu/game/loadinfo")

    def test_private_unknown_and_wrong_id_fail_closed(self) -> None:
        game = {"id": 99911, "turn": 4, "isprivate": False}
        payload = {"game": game, "players": []}
        self.assertIsNone(
            public_roster_from_loadinfo(
                {"game": {**game, "isprivate": True}, "players": []}, 99911
            )
        )
        self.assertIsNone(
            public_roster_from_loadinfo(
                {"game": {"id": 99911}, "players": []}, 99911
            )
        )
        self.assertIsNone(public_roster_from_loadinfo(payload, 99912))

    def test_ambiguous_duplicate_identity_excluded(self) -> None:
        payload = {
            "game": {"id": 99911, "turn": 4, "isprivate": False},
            "players": [
                {"id": 1, "username": "ALPHA", "raceid": 2, "status": 1},
                {"id": 2, "username": " alpha ", "raceid": 5, "status": 1},
                {"id": 3, "username": "Beta", "raceid": 4, "status": 1},
            ],
        }
        result = public_roster_from_loadinfo(payload, 99911)
        self.assertIsNotNone(result)
        self.assertEqual([p["username"] for p in result[1]], ["Beta"])
