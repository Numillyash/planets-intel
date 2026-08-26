import unittest

from app.scripts.combat_right_balance_evidence import (
    _ammo_mass_isolated,
    _candidate_shape,
    _classify_delta,
)


class CombatRightBalanceEvidenceTests(unittest.TestCase):
    def test_candidate_shape_requires_left_carrier_and_two_ships(self) -> None:
        payload = {
            "left": {"hullid": 99, "baycount": 8},
            "right": {"hullid": 23, "mass": 450},
        }
        self.assertTrue(_candidate_shape(payload))

        no_carrier = {
            "left": {"hullid": 99, "baycount": 0},
            "right": {"hullid": 23, "mass": 450},
        }
        self.assertFalse(_candidate_shape(no_carrier))

    def test_ammo_mass_isolation_requires_no_right_launchers_or_bays(self) -> None:
        self.assertTrue(
            _ammo_mass_isolated(
                {"right": {"launchercount": 0, "baycount": 0}}
            )
        )
        self.assertFalse(
            _ammo_mass_isolated(
                {"right": {"launchercount": 4, "baycount": 0}}
            )
        )
        self.assertFalse(
            _ammo_mass_isolated(
                {"right": {"launchercount": 0, "baycount": 8}}
            )
        )

    def test_mass_delta_classification_keeps_evidence_tiers_separate(self) -> None:
        self.assertEqual(
            _classify_delta(vcr_mass=860, observed_mass=500, owner_observed=True),
            "exact_bonus_applied",
        )
        self.assertEqual(
            _classify_delta(vcr_mass=500, observed_mass=500, owner_observed=True),
            "exact_bonus_not_applied",
        )
        self.assertEqual(
            _classify_delta(vcr_mass=860, observed_mass=500, owner_observed=False),
            "supporting_bonus_applied",
        )
        self.assertEqual(
            _classify_delta(vcr_mass=700, observed_mass=500, owner_observed=True),
            "exact_other_delta",
        )


if __name__ == "__main__":
    unittest.main()
