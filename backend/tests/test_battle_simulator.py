import random
import unittest

from app.services.battle_simulator import (
    _balance_applied,
    _balance_probability,
    _combatant_payload,
    _fed_recover_shields,
    _functional_weapon_limit,
    _prepare_sequence_combatant,
    _right_balance_eligible,
    _sequence_planet_is_unsupported,
    _with_right_balance_bonus,
)


class BattleSimulatorHelperTests(unittest.TestCase):
    def test_planet_starbase_flag_is_explicit(self) -> None:
        plain = _combatant_payload(
            {
                "source_kind": "known_planet",
                "hull_id": 0,
                "has_starbase": False,
                "mass": 100,
            }
        )
        base = _combatant_payload(
            {
                "source_kind": "known_planet",
                "hull_id": 0,
                "has_starbase": True,
                "mass": 200,
            }
        )

        self.assertFalse(plain["hasstarbase"])
        self.assertTrue(base["hasstarbase"])

    def test_right_balance_requires_ship_carrier_left_and_heavy_ship_right(self) -> None:
        carrier = {"hull_id": 10, "bay_count": 6, "mass": 200}
        heavy_ship = {"hull_id": 20, "bay_count": 0, "mass": 140}
        light_ship = {"hull_id": 21, "bay_count": 0, "mass": 139}
        planet = {"hull_id": 0, "bay_count": 10, "mass": 300}

        self.assertTrue(_right_balance_eligible(carrier, heavy_ship))
        self.assertFalse(_right_balance_eligible(carrier, light_ship))
        self.assertFalse(_right_balance_eligible(planet, heavy_ship))
        self.assertFalse(
            _right_balance_eligible(
                {"hull_id": 10, "bay_count": 0, "mass": 200},
                heavy_ship,
            )
        )

    def test_right_balance_modes_are_explicit_and_eligibility_gated(self) -> None:
        rng = random.Random(12345)

        self.assertTrue(_balance_applied(eligible=True, mode="on", rng=rng))
        self.assertFalse(_balance_applied(eligible=True, mode="off", rng=rng))
        self.assertFalse(_balance_applied(eligible=False, mode="on", rng=rng))
        self.assertEqual(_balance_probability(True, "on"), 1.0)
        self.assertEqual(_balance_probability(True, "off"), 0.0)
        self.assertEqual(_balance_probability(True, "auto"), 0.60)
        self.assertEqual(_balance_probability(False, "auto"), 0.0)

    def test_right_balance_adds_mass_without_mutating_source_payload(self) -> None:
        payload = {
            "left": {"mass": 200},
            "right": {"mass": 160},
        }

        adjusted = _with_right_balance_bonus(payload, applied=True)

        self.assertEqual(payload["right"]["mass"], 160)
        self.assertEqual(adjusted["right"]["mass"], 520)

    def test_damage_reduces_non_fed_weapons_but_not_fed_weapons(self) -> None:
        normal = {
            "race_id": 3,
            "damage": 56,
            "federation_crew_bonus": False,
        }
        fed = {
            "race_id": 1,
            "damage": 56,
            "federation_crew_bonus": True,
        }
        lizard = {
            "race_id": 2,
            "damage": 76,
            "federation_crew_bonus": False,
        }

        self.assertEqual(_functional_weapon_limit(normal), 5)
        self.assertEqual(_functional_weapon_limit(fed), 10)
        self.assertEqual(_functional_weapon_limit(lizard), 8)

    def test_sequence_preparation_rebuilds_effective_weapons_from_physical_hull(self) -> None:
        raw = {
            "hull_id": 10,
            "race_id": 3,
            "damage": 56,
            "physical_beam_count": 10,
            "physical_launcher_count": 8,
            "physical_bay_count": 7,
            "beam_count": 10,
            "launcher_count": 8,
            "bay_count": 7,
        }

        prepared = _prepare_sequence_combatant(raw)

        self.assertEqual(prepared["beam_count"], 5)
        self.assertEqual(prepared["launcher_count"], 5)
        self.assertEqual(prepared["bay_count"], 5)
        self.assertEqual(raw["beam_count"], 10)

    def test_fed_recovers_quarter_of_lost_shields_between_fights(self) -> None:
        fed = {
            "federation_crew_bonus": True,
            "shield": 40,
        }
        normal = {
            "federation_crew_bonus": False,
            "shield": 40,
        }

        recovered = _fed_recover_shields(fed)
        normal_recovered = _fed_recover_shields(normal)

        self.assertEqual(recovered, 15)
        self.assertEqual(fed["shield"], 55)
        self.assertEqual(normal_recovered, 0)
        self.assertEqual(normal["shield"], 40)

    def test_planet_multiwave_is_fail_closed(self) -> None:
        ship = {"hull_id": 10}
        planet = {"hull_id": 0}

        self.assertFalse(_sequence_planet_is_unsupported([ship], [planet]))
        self.assertTrue(_sequence_planet_is_unsupported([ship, ship], [planet]))
        self.assertTrue(_sequence_planet_is_unsupported([ship], [ship, planet]))


if __name__ == "__main__":
    unittest.main()
