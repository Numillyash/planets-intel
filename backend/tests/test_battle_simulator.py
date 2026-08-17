import unittest

from app.services.battle_simulator import (
    _combatant_payload,
    _right_balance_eligible,
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

    def test_right_balance_adds_mass_without_mutating_source_payload(self) -> None:
        payload = {
            "left": {"mass": 200},
            "right": {"mass": 160},
        }

        adjusted = _with_right_balance_bonus(payload, applied=True)

        self.assertEqual(payload["right"]["mass"], 160)
        self.assertEqual(adjusted["right"]["mass"], 520)


if __name__ == "__main__":
    unittest.main()
