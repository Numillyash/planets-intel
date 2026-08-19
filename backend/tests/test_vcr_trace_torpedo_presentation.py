import unittest

from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog
from app.services.vcr_replay_trace import replay_nuhost_trace


BEAMS = []
TORPEDOES = [
    {
        "id": 6,
        "name": "Mark 4 Photon",
        "crewkill": 13,
        "damage": 30,
        "combatrange": 300,
    }
]
SETTINGS = {"combatrng": 0}


def _payload() -> dict:
    return {
        "id": 501,
        "turn": 1,
        "seed": 49,
        "battletype": 1,
        "leftownerid": 1,
        "rightownerid": 2,
        "left": {
            "objectid": 1,
            "name": "TORP SOURCE",
            "beamcount": 0,
            "launchercount": 2,
            "baycount": 0,
            "hullid": 37,
            "beamid": 0,
            "torpedoid": 6,
            "shield": 100,
            "damage": 0,
            "crew": 525,
            "mass": 275,
            "raceid": 4,
            "beamkillbonus": 1,
            "beamchargerate": 1,
            "torpchargerate": 1,
            "torpmisspercent": 35,
            "crewdefensepercent": 0,
            "torpedos": 8,
            "fighters": 0,
            "hasstarbase": False,
        },
        "right": {
            "objectid": 2,
            "name": "TORP TARGET",
            "beamcount": 0,
            "launchercount": 0,
            "baycount": 0,
            "hullid": 2,
            "beamid": 0,
            "torpedoid": 0,
            "shield": 100,
            "damage": 0,
            "crew": 1000,
            "mass": 200,
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


class VcrTraceTorpedoPresentationTests(unittest.TestCase):
    def test_torpedo_events_expose_factual_hit_boolean_without_changing_combat(self) -> None:
        payload = _payload()
        plain = replay_nuhost_from_nu_catalog(
            payload,
            beams=BEAMS,
            torpedoes=TORPEDOES,
            settings=SETTINGS,
        )
        traced = replay_nuhost_trace(
            payload,
            beams=BEAMS,
            torpedoes=TORPEDOES,
            settings=SETTINGS,
        )

        self.assertEqual(traced["result"], plain["result"])
        self.assertEqual(traced["cycles"], plain["cycles"])

        torpedo_events = [
            effect
            for frame in traced["frames"]
            for effect in frame.get("effects", [])
            if effect.get("kind") == "torpedo_launch"
        ]
        self.assertTrue(torpedo_events)
        self.assertTrue(all(isinstance(effect.get("hit"), bool) for effect in torpedo_events))
        self.assertTrue(all(isinstance(effect.get("source_x"), int) for effect in torpedo_events))
        self.assertTrue(all(isinstance(effect.get("target_x"), int) for effect in torpedo_events))

        final = traced["frames"][-1]
        for side_name in ("left", "right"):
            for field in ("shield", "damage", "crew", "torpedoes", "fighters"):
                self.assertEqual(final[side_name][field], plain[side_name][field])


if __name__ == "__main__":
    unittest.main()
