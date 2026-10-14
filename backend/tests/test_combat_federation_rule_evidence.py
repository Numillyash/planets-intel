import unittest

from app.scripts.combat_federation_rule_evidence import (
    _normal_damage_weapon_limit,
    _repeated_same_turn_transitions,
    _side_record,
)


class CombatFederationRuleEvidenceTests(unittest.TestCase):
    def test_normal_damage_limit(self) -> None:
        self.assertEqual(_normal_damage_weapon_limit(0), 10)
        self.assertEqual(_normal_damage_weapon_limit(19), 9)
        self.assertEqual(_normal_damage_weapon_limit(50), 5)
        self.assertEqual(_normal_damage_weapon_limit(100), 0)

    def test_damaged_fed_direct_evidence_when_count_exceeds_normal_limit(self) -> None:
        payload = {
            "left": {
                "hullid": 10,
                "raceid": 1,
                "objectid": 5,
                "name": "Fed ship",
                "damage": 50,
                "shield": 0,
                "beamcount": 6,
                "launchercount": 4,
                "baycount": 0,
            }
        }
        case = _side_record(
            game_id=1,
            turn=2,
            vcr_id=3,
            side_name="left",
            payload=payload,
            hulls={10: {"id": 10, "fighterbays": 0}},
            x=100,
            y=200,
        )
        self.assertIsNotNone(case)
        assert case is not None
        self.assertEqual(case["damaged_weapon_continuity"]["status"], "direct_evidence")

    def test_carrier_bay_bonus_compares_hull_bays_plus_three(self) -> None:
        payload = {
            "right": {
                "hullid": 20,
                "raceid": 1,
                "objectid": 6,
                "name": "Fed carrier",
                "damage": 0,
                "shield": 100,
                "beamcount": 4,
                "launchercount": 0,
                "baycount": 9,
            }
        }
        case = _side_record(
            game_id=1,
            turn=2,
            vcr_id=4,
            side_name="right",
            payload=payload,
            hulls={20: {"id": 20, "fighterbays": 6}},
            x=100,
            y=200,
        )
        self.assertIsNotNone(case)
        assert case is not None
        self.assertEqual(case["carrier_bay_bonus"]["status"], "match")
        self.assertEqual(case["carrier_bay_bonus"]["delta"], 3)

    def test_repeated_transitions_require_same_turn_ship_and_position(self) -> None:
        cases = [
            {
                "game_id": 1,
                "turn": 7,
                "vcr_id": 10,
                "ship_id": 42,
                "position": [100, 200],
                "start": {"shield": 50},
            },
            {
                "game_id": 1,
                "turn": 7,
                "vcr_id": 11,
                "ship_id": 42,
                "position": [100, 200],
                "start": {"shield": 30},
            },
            {
                "game_id": 1,
                "turn": 7,
                "vcr_id": 12,
                "ship_id": 42,
                "position": [101, 200],
                "start": {"shield": 20},
            },
        ]
        transitions = _repeated_same_turn_transitions(cases)
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0]["from_vcr"], 10)
        self.assertEqual(transitions[0]["to_vcr"], 11)


if __name__ == "__main__":
    unittest.main()
