import unittest

from app.scripts.combat_corpus_coverage import _case_profile, _side_profile


class CombatCorpusCoverageTests(unittest.TestCase):
    def test_side_profile_preserves_known_zero_and_classifies_carrier(self) -> None:
        profile = _side_profile(
            {
                "objectid": 19,
                "name": "VIRGO CLASS BATTLESTAR",
                "hullid": 67,
                "raceid": 11,
                "beamcount": 0,
                "launchercount": 0,
                "baycount": 8,
                "mass": 1540,
                "damage": 0,
                "shield": 100,
                "hasstarbase": False,
            }
        )

        self.assertEqual(profile["kind"], "ship")
        self.assertEqual(profile["beam_count"], 0)
        self.assertTrue(profile["carrier"])
        self.assertFalse(profile["torpedo_ship"])
        self.assertFalse(profile["unarmed_ship"])

    def test_ship_vs_starbase_shape_is_factual_input_classification(self) -> None:
        profile = _case_profile(
            {
                "left": {
                    "objectid": 7,
                    "hullid": 10,
                    "raceid": 2,
                    "beamcount": 4,
                    "launchercount": 2,
                    "baycount": 0,
                    "mass": 200,
                    "damage": 12,
                    "shield": 73,
                    "hasstarbase": False,
                },
                "right": {
                    "objectid": 90,
                    "hullid": 0,
                    "raceid": 4,
                    "beamcount": 10,
                    "launchercount": 0,
                    "baycount": 10,
                    "mass": 375,
                    "damage": 0,
                    "shield": 100,
                    "hasstarbase": True,
                },
            }
        )

        self.assertEqual(profile["shape"], "ship_vs_planet")
        self.assertTrue(profile["ship_vs_planet"])
        self.assertTrue(profile["starbase_battle"])
        self.assertTrue(profile["lizard_ship_battle"])
        self.assertTrue(profile["lizard_ship_vs_planet"])
        self.assertTrue(profile["damaged_start"])
        self.assertTrue(profile["sub_full_shield_start"])

    def test_right_balance_candidate_shape_matches_current_simulator_predicate(self) -> None:
        eligible = _case_profile(
            {
                "left": {
                    "hullid": 10,
                    "raceid": 3,
                    "beamcount": 4,
                    "launchercount": 0,
                    "baycount": 6,
                    "mass": 200,
                },
                "right": {
                    "hullid": 20,
                    "raceid": 4,
                    "beamcount": 8,
                    "launchercount": 4,
                    "baycount": 0,
                    "mass": 140,
                },
            }
        )
        light_right = _case_profile(
            {
                "left": {
                    "hullid": 10,
                    "raceid": 3,
                    "beamcount": 4,
                    "launchercount": 0,
                    "baycount": 6,
                    "mass": 200,
                },
                "right": {
                    "hullid": 21,
                    "raceid": 4,
                    "beamcount": 2,
                    "launchercount": 0,
                    "baycount": 0,
                    "mass": 139,
                },
            }
        )

        self.assertTrue(eligible["right_balance_candidate_shape"])
        self.assertFalse(light_right["right_balance_candidate_shape"])

    def test_unarmed_ship_requires_all_physical_weapon_counts_zero(self) -> None:
        profile = _side_profile(
            {
                "hullid": 5,
                "raceid": 6,
                "beamcount": 0,
                "launchercount": 0,
                "baycount": 0,
                "mass": 80,
            }
        )
        self.assertTrue(profile["unarmed_ship"])


if __name__ == "__main__":
    unittest.main()
