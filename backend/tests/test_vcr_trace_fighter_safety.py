import unittest

from app.services.vcr_replay import CombatObject
from app.services.vcr_replay_nu import replay_nuhost_from_nu_catalog
from app.services.vcr_replay_trace import (
    TracingNuHostClassicReplay,
    replay_nuhost_trace,
)


SETTINGS = {"combatrng": 0}


def _fighter_payload():
    return {
        "id": 99,
        "turn": 1,
        "seed": 1,
        "battletype": 1,
        "leftownerid": 1,
        "rightownerid": 2,
        "left": {
            "objectid": 1,
            "name": "TRACE CARRIER",
            "beamcount": 0,
            "launchercount": 0,
            "baycount": 10,
            "hullid": 1,
            "beamid": 0,
            "torpedoid": 0,
            "shield": 100,
            "damage": 0,
            "crew": 100,
            "mass": 100,
            "raceid": 3,
            "beamkillbonus": 1,
            "beamchargerate": 1,
            "torpchargerate": 1,
            "torpmisspercent": 35,
            "crewdefensepercent": 0,
            "torpedos": 0,
            "fighters": 5,
            "hasstarbase": False,
        },
        "right": {
            "objectid": 2,
            "name": "TRACE TARGET",
            "beamcount": 0,
            "launchercount": 0,
            "baycount": 0,
            "hullid": 2,
            "beamid": 0,
            "torpedoid": 0,
            "shield": 100,
            "damage": 0,
            "crew": 100,
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


def _combat_object(object_id: int) -> CombatObject:
    return CombatObject(
        object_id=object_id,
        owner_id=object_id,
        name=f"Object {object_id}",
        beam_count=0,
        launcher_count=0,
        bay_count=0,
        hull_id=object_id,
        beam_id=0,
        torpedo_id=0,
        shield=100,
        damage=0,
        crew=100,
        mass=100,
        race_id=3,
        beam_kill_rate=1,
        beam_charge_rate=1,
        torp_charge_rate=1,
        torp_miss_rate=35,
        crew_defense_rate=0,
        torpedoes=0,
        fighters=0,
        is_planet=False,
    )


class VcrTraceFighterSafetyTests(unittest.TestCase):
    def test_fighter_visual_trace_keeps_terminal_result_identical(self) -> None:
        payload = _fighter_payload()
        plain = replay_nuhost_from_nu_catalog(
            payload,
            beams=[],
            torpedoes=[],
            settings=SETTINGS,
        )
        traced = replay_nuhost_trace(
            payload,
            beams=[],
            torpedoes=[],
            settings=SETTINGS,
        )

        self.assertEqual(traced["result"], plain["result"])
        self.assertEqual(traced["cycles"], plain["cycles"])
        final = traced["frames"][-1]
        for side_name in ("left", "right"):
            for field in ("shield", "damage", "crew", "torpedoes", "fighters"):
                self.assertEqual(final[side_name][field], plain[side_name][field])

        kinds = {
            effect["kind"]
            for frame in traced["frames"]
            for effect in frame.get("effects", [])
        }
        self.assertIn("fighter_launch", kinds)
        self.assertIn("fighter_attack", kinds)

    def test_trace_exposes_exact_presentation_metadata(self) -> None:
        traced = replay_nuhost_trace(
            _fighter_payload(),
            beams=[],
            torpedoes=[],
            settings=SETTINGS,
        )
        first = traced["frames"][0]
        left = first["left"]
        right = first["right"]

        self.assertEqual(left["bay_count"], 10)
        self.assertEqual(right["bay_count"], 0)
        self.assertEqual(left["damage_limit"], 100)
        self.assertEqual(right["damage_limit"], 100)
        self.assertFalse(left["destroyed"])
        self.assertFalse(right["destroyed"])
        self.assertEqual(left["beam_slots"], [])
        self.assertEqual(left["launcher_slots"], [])

        for frame in traced["frames"]:
            for side_name in ("left", "right"):
                side = frame[side_name]
                self.assertIn("damage_limit", side)
                self.assertIn("destroyed", side)
                self.assertIn("bay_count", side)

    def test_dogfight_kill_hook_emits_presentation_event_without_rng(self) -> None:
        engine = TracingNuHostClassicReplay(
            seed=17,
            left=_combat_object(1),
            right=_combat_object(2),
            beams={},
            torpedoes={},
        )
        side = engine.status[0]
        side.fighter_status[0] = 1
        side.fighter_x[0] = 320
        side.num_fighters_out = 1
        seed_before = engine.seed

        engine._fighter_kill_context = "dogfight"
        engine._kill_fighter(side, 0)

        self.assertEqual(engine.seed, seed_before)
        self.assertEqual(side.fighter_status[0], 0)
        self.assertEqual(side.num_fighters_out, 0)
        self.assertEqual(
            engine.cycle_effects,
            [
                {
                    "kind": "fighter_dogfight_loss",
                    "lost_side": "left",
                    "fighter_id": 0,
                    "x": 320,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
