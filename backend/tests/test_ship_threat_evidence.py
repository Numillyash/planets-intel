import unittest
from app.services.ship_threat_evidence import (
    compatible_vcr_side, defender_ammo, full_tank_scenario,
    hull_fuel_capacity, uniform_beam_fighter_scenarios,
)

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


    def test_gorbie_fuel_key_aliases_do_not_depend_on_catalog_spelling(self):
        self.assertEqual(hull_fuel_capacity({"fuel":1760}), 1760)
        self.assertEqual(hull_fuel_capacity({"fueltank":1760}), 1760)
        self.assertEqual(hull_fuel_capacity({"fuelcapacity":1760}), 1760)
        self.assertEqual(hull_fuel_capacity({"FuelTank":1760}), 1760)
        self.assertEqual(hull_fuel_capacity({"fueltank":0}), 0)
        self.assertIsNone(hull_fuel_capacity({"cargo":250}))
        self.assertIsNone(hull_fuel_capacity(None))

    def test_ten_uniform_beams_bound_fighters_under_full_fuel(self):
        records=[
            {"id":1,"name":"Laser","techlevel":1,"mass":1},
            {"id":2,"name":"X-Ray Laser","techlevel":1,"mass":1},
            {"id":3,"name":"Plasma Bolt","techlevel":2,"mass":2},
            {"id":4,"name":"Blaster","techlevel":3,"mass":4},
            {"id":5,"name":"Positron Beam","techlevel":4,"mass":3},
            {"id":6,"name":"Disruptor","techlevel":5,"mass":4},
            {"id":7,"name":"Heavy Blaster","techlevel":6,"mass":7},
            {"id":8,"name":"Phaser","techlevel":7,"mass":5},
            {"id":9,"name":"Heavy Disruptor","techlevel":8,"mass":7},
            {"id":10,"name":"Heavy Phaser","techlevel":10,"mass":6},
        ]
        rows=uniform_beam_fighter_scenarios(
            mass=2803,bare_mass=980,fuel_capacity=1760,
            beam_slots=10,fighter_bays=10,beams=records)
        by_name={row["beam_name"]:row for row in rows}
        self.assertEqual(len(rows),10)
        self.assertEqual([by_name[n]["fighter_ceiling"] for n in (
            "Laser","X-Ray Laser","Plasma Bolt","Positron Beam",
            "Blaster","Disruptor","Phaser","Heavy Phaser"
        )],[53,53,43,33,23,23,13,3])
        self.assertIsNone(by_name["Heavy Blaster"]["fighter_ceiling"])
        self.assertFalse(by_name["Heavy Disruptor"]["full_tank_compatible"])
        self.assertEqual(by_name["Disruptor"]["beam_mass_total"],40)
        self.assertEqual(by_name["Heavy Phaser"]["beam_count_assumed"],10)

    def test_scenarios_fail_closed_when_fuel_or_weapon_mass_unknown(self):
        self.assertEqual(uniform_beam_fighter_scenarios(
            mass=2803,bare_mass=980,fuel_capacity=None,
            beam_slots=10,fighter_bays=10,beams=[{"id":6,"mass":4}]), [])
        self.assertEqual(uniform_beam_fighter_scenarios(
            mass=2803,bare_mass=980,fuel_capacity=1760,
            beam_slots=10,fighter_bays=0,beams=[{"id":6,"mass":4}]), [])
        self.assertEqual(uniform_beam_fighter_scenarios(
            mass=2803,bare_mass=980,fuel_capacity=1760,
            beam_slots=10,fighter_bays=10,beams=[{"id":6,"name":"Disruptor"}]), [])
        self.assertEqual(uniform_beam_fighter_scenarios(
            mass=1200,bare_mass=980,fuel_capacity=1760,
            beam_slots=10,fighter_bays=10,beams=[{"id":6,"mass":4}]), [])

    def test_virgo_crosscheck_mass_after_fighters_and_ten_disruptors(self):
        scenario=full_tank_scenario(
            mass=2321,bare_mass=625,fuel_capacity=1550,fighter_bays=8)
        self.assertEqual(scenario["remaining_mass_ceiling"],146)
        self.assertEqual(scenario["remaining_mass_ceiling"]-106-10*4,0)


if __name__=="__main__":
    unittest.main()
