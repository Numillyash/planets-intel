import unittest
from app.services.ship_threat_evidence import compatible_vcr_side, defender_ammo, full_tank_scenario

class ShipThreatEvidenceTests(unittest.TestCase):
    def test_gorbie_cannot_inherit_torpedo_tubes_from_vcr(self):
        self.assertFalse(compatible_vcr_side(
            {"hullid":70, "beamcount":4, "launchercount":2, "torpedoid":5, "torpedos":0},
            hull_id=70, beam_slots=10, tube_slots=0, fighter_bays=10))
        self.assertFalse(compatible_vcr_side(
            {"hullid":71, "beamcount":4, "launchercount":0},
            hull_id=70, beam_slots=10, tube_slots=0, fighter_bays=10))
        self.assertTrue(compatible_vcr_side(
            {"hullid":70, "beamcount":10, "launchercount":0, "torpedoid":0},
            hull_id=70, beam_slots=10, tube_slots=0, fighter_bays=10))

    def test_generic_private_ammo_is_fighter_stock_only_for_carrier(self):
        record=defender_ammo({"ammo":76}, fighter_bays=8, tube_slots=0)
        self.assertEqual(record["fighters"],76)
        self.assertEqual(record["fighter_basis"],"generic_ammo_carrier")
        self.assertIsNone(record["torpedoes"])
        self.assertEqual(defender_ammo({"ammo":0}, fighter_bays=8, tube_slots=0)["fighters"],0)
        self.assertIsNone(defender_ammo({}, fighter_bays=8, tube_slots=0)["fighters"])
        self.assertEqual(defender_ammo({"ammo":45,"fighters":0},fighter_bays=8,tube_slots=0)["fighters"],0)
        self.assertIsNone(defender_ammo({"ammo":45},fighter_bays=8,tube_slots=2)["fighters"])
        self.assertEqual(defender_ammo({"ammo":45},fighter_bays=0,tube_slots=2)["torpedoes"],45)

    def test_full_tank_is_conditional_not_observed(self):
        s=full_tank_scenario(mass=2803,bare_mass=980,fuel_capacity=1760,fighter_bays=10)
        self.assertTrue(s["feasible"])
        self.assertEqual(s["remaining_mass_ceiling"],63)
        self.assertEqual(s["fighter_ceiling"],63)
        s=full_tank_scenario(mass=1000,bare_mass=980,fuel_capacity=1760,fighter_bays=10)
        self.assertFalse(s["feasible"])
        self.assertIsNone(s["fighter_ceiling"])
        self.assertIsNone(full_tank_scenario(mass=None,bare_mass=980,fuel_capacity=1760,fighter_bays=10))

if __name__=="__main__":
    unittest.main()
