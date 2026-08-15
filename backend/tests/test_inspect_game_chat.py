import unittest

from app.scripts.inspect_game_chat import activity_request_candidates


class ActivityProbeCandidateTests(unittest.TestCase):
    def test_player_id_is_present_in_every_candidate(self) -> None:
        candidates = activity_request_candidates(
            api_key="secret",
            planets_account_id=33734,
            game_id=682932,
            player_id=7,
        )

        self.assertGreaterEqual(len(candidates), 1)
        for _label, payload in candidates:
            self.assertEqual(payload["gameid"], 682932)
            self.assertEqual(payload["playerid"], 7)
            self.assertEqual(payload["apikey"], "secret")

    def test_account_id_candidate_is_optional(self) -> None:
        candidates = activity_request_candidates(
            api_key="secret",
            planets_account_id=None,
            game_id=682932,
            player_id=7,
        )

        self.assertEqual(
            candidates,
            [
                (
                    "apikey+gameid+playerid",
                    {
                        "apikey": "secret",
                        "gameid": 682932,
                        "playerid": 7,
                    },
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
