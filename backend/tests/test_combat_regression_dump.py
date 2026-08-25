import unittest

from app.models.combat_state_observation import CombatStateObservation
from app.scripts.combat_regression_dump import (
    _compare_analyst_state,
    _payload_hash,
    _side_summary,
)


class CombatRegressionDumpTests(unittest.TestCase):
    def test_payload_hash_is_order_independent(self) -> None:
        left = {"seed": 7, "left": {"objectid": 10, "hullid": 20}}
        right = {"left": {"hullid": 20, "objectid": 10}, "seed": 7}

        self.assertEqual(_payload_hash(left), _payload_hash(right))

    def test_side_summary_preserves_known_zero(self) -> None:
        summary = _side_summary(
            {
                "left": {
                    "objectid": 19,
                    "name": "VIRGO CLASS BATTLESTAR",
                    "hullid": 67,
                    "raceid": 11,
                    "beamcount": 0,
                    "launchercount": 0,
                    "baycount": 8,
                    "torpedos": 0,
                    "fighters": 80,
                    "shield": 100,
                    "damage": 0,
                    "crew": 1800,
                    "mass": 1540,
                }
            },
            "left",
        )

        self.assertTrue(summary["present"])
        self.assertEqual(summary["beam_count"], 0)
        self.assertEqual(summary["launcher_count"], 0)
        self.assertEqual(summary["torpedoes"], 0)
        self.assertEqual(summary["fighters"], 80)

    def test_analyst_validation_matches_only_asserted_values(self) -> None:
        payload = {
            "left": {"objectid": 7, "hullid": 10},
            "right": {"objectid": 90, "hullid": 0},
        }
        replay = {
            "left": {"torpedoes": 4, "fighters": 12},
            "right": {"torpedoes": 0, "fighters": 0},
        }
        row = CombatStateObservation(
            user_id=1,
            game_id=2,
            turn=3,
            vcr_id=4,
            ship_id=7,
            post_combat_torpedoes=4,
            post_combat_fighters=None,
            note=None,
        )

        checks = _compare_analyst_state(
            payload=payload,
            replay=replay,
            rows=[row],
        )

        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["status"], "match")
        self.assertEqual(checks[0]["asserted"], {"torpedoes": 4})
        self.assertEqual(checks[0]["replay"], {"torpedoes": 4})

    def test_analyst_validation_reports_field_mismatch(self) -> None:
        payload = {
            "left": {"objectid": 7, "hullid": 10},
            "right": {"objectid": 90, "hullid": 0},
        }
        replay = {
            "left": {"torpedoes": 3, "fighters": 11},
            "right": {"torpedoes": 0, "fighters": 0},
        }
        row = CombatStateObservation(
            user_id=1,
            game_id=2,
            turn=3,
            vcr_id=4,
            ship_id=7,
            post_combat_torpedoes=4,
            post_combat_fighters=11,
            note="manual review",
        )

        checks = _compare_analyst_state(
            payload=payload,
            replay=replay,
            rows=[row],
        )

        self.assertEqual(checks[0]["status"], "mismatch")
        self.assertEqual(checks[0]["mismatches"], ["torpedoes"])
        self.assertEqual(checks[0]["note"], "manual review")


if __name__ == "__main__":
    unittest.main()
