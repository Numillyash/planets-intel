import unittest

from app.services.vcr_replay import ReplayUnsupported
from app.services.vcr_replay_nu import (
    normalize_nu_torpedoes,
    replay_nuhost_from_nu_catalog,
)


BEAMS = [
    {"id": 1, "name": "Laser", "crewkill": 10, "damage": 3},
    {"id": 2, "name": "X-Ray Laser", "crewkill": 15, "damage": 1},
    {"id": 3, "name": "Plasma Bolt", "crewkill": 3, "damage": 10},
    {"id": 4, "name": "Blaster", "crewkill": 10, "damage": 25},
    {"id": 5, "name": "Positron Beam", "crewkill": 9, "damage": 29},
    {"id": 6, "name": "Disruptor", "crewkill": 30, "damage": 20},
    {"id": 7, "name": "Heavy Blaster", "crewkill": 20, "damage": 40},
]

# These records intentionally use the real Planets.nu RST field names and the
# values observed in game 682909's persisted GameRuleCatalog.
TORPEDOES = [
    {
        "id": 5,
        "name": "Mark 3c Photon",
        "crewkill": 9,
        "damage": 25,
        "combatrange": 300,
    },
    {
        "id": 6,
        "name": "Mark 4 Photon",
        "crewkill": 13,
        "damage": 30,
        "combatrange": 300,
    },
]

CLASSIC_SETTINGS = {"combatrng": 0}


def vcr2():
    return {
        "id": 2,
        "turn": 8,
        "seed": 49,
        "battletype": 1,
        "x": 1816,
        "y": 2175,
        "leftownerid": 4,
        "rightownerid": 3,
        "left": {
            "objectid": 20,
            "name": "ILL WIND CLASS BATTLECRUISER",
            "beamcount": 10,
            "launchercount": 2,
            "baycount": 0,
            "hullid": 37,
            "beamid": 7,
            "torpedoid": 6,
            "shield": 100,
            "damage": 0,
            "crew": 525,
            "mass": 275,
            "raceid": 4,
            "beamkillbonus": 1,
            "beamchargerate": 2,
            "torpchargerate": 1,
            "torpmisspercent": 35,
            "crewdefensepercent": 0,
            "torpedos": 5,
            "fighters": 0,
            "hasstarbase": False,
        },
        "right": {
            "objectid": 35,
            "name": "Fantasia",
            "beamcount": 0,
            "launchercount": 0,
            "baycount": 0,
            "hullid": 0,
            "beamid": 1,
            "torpedoid": 0,
            "shield": 0,
            "damage": 0,
            "crew": 10000,
            "mass": 100,
            "raceid": 3,
            "beamkillbonus": 1,
            "beamchargerate": 1,
            "torpchargerate": 1,
            "torpmisspercent": 35,
            "crewdefensepercent": 0,
            "torpedos": 0,
            "fighters": 0,
            "hasstarbase": False,
        },
    }


def vcr3():
    return {
        "id": 3,
        "turn": 8,
        "seed": 55,
        "battletype": 1,
        "x": 1836,
        "y": 2187,
        "leftownerid": 4,
        "rightownerid": 3,
        "left": {
            "objectid": 39,
            "name": "ILL WIND CLASS BATTLECRUISER",
            "beamcount": 10,
            "launchercount": 2,
            "baycount": 0,
            "hullid": 37,
            "beamid": 7,
            "torpedoid": 5,
            "shield": 100,
            "damage": 0,
            "crew": 525,
            "mass": 275,
            "raceid": 4,
            "beamkillbonus": 1,
            "beamchargerate": 2,
            "torpchargerate": 1,
            "torpmisspercent": 35,
            "crewdefensepercent": 0,
            "torpedos": 0,
            "fighters": 0,
            "hasstarbase": False,
        },
        "right": {
            "objectid": 74,
            "name": "New Bohemia",
            "beamcount": 5,
            "launchercount": 0,
            "baycount": 9,
            "hullid": 0,
            "beamid": 7,
            "torpedoid": 0,
            "shield": 100,
            "damage": 0,
            "crew": 10000,
            "mass": 186,
            "raceid": 3,
            "beamkillbonus": 1,
            "beamchargerate": 1,
            "torpchargerate": 1,
            "torpmisspercent": 35,
            "crewdefensepercent": 0,
            "torpedos": 0,
            "fighters": 9,
            "hasstarbase": False,
        },
    }


class NuHostClassicReplayTests(unittest.TestCase):
    def test_nu_torpedo_catalog_mapping(self):
        mapped = normalize_nu_torpedoes(TORPEDOES)
        mark4 = next(item for item in mapped if item["id"] == 6)
        self.assertEqual(mark4["damage"], 30)
        self.assertEqual(mark4["kill"], 13)
        self.assertEqual(mark4["firingrangebonus"], 0)

    def test_vcr2_consumes_all_five_mark4_torpedoes(self):
        result = replay_nuhost_from_nu_catalog(
            vcr2(),
            beams=BEAMS,
            torpedoes=TORPEDOES,
            settings=CLASSIC_SETTINGS,
        )
        self.assertEqual(result["left"]["torpedoes"], 0)
        self.assertTrue(result["left"]["survived"])
        self.assertIn("right_destroyed", result["result"])

    def test_vcr3_no_torpedoes_and_ship_survives_planet_fighters(self):
        result = replay_nuhost_from_nu_catalog(
            vcr3(),
            beams=BEAMS,
            torpedoes=TORPEDOES,
            settings=CLASSIC_SETTINGS,
        )
        self.assertEqual(result["left"]["torpedoes"], 0)
        self.assertEqual(result["left"]["shield"], 29)
        self.assertEqual(result["left"]["damage"], 0)
        self.assertEqual(result["left"]["crew"], 525)
        self.assertTrue(result["left"]["survived"])
        self.assertEqual(result["right"]["fighters"], 0)
        self.assertIn("right_destroyed", result["result"])

    def test_extended_combat_rng_is_rejected(self):
        with self.assertRaises(ReplayUnsupported):
            replay_nuhost_from_nu_catalog(
                vcr2(),
                beams=BEAMS,
                torpedoes=TORPEDOES,
                settings={"combatrng": 1},
            )


if __name__ == "__main__":
    unittest.main()
