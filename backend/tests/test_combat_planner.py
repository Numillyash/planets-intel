import unittest

from app.services.combat_replay_trace import apply_combat_scenario_overrides
from app.services.vcr_replay import ReplayUnsupported


class CombatPlannerScenarioTests(unittest.TestCase):
    def test_overrides_clone_payload_without_mutating_fact(self) -> None:
        payload = {
            "seed": 17,
            "left": {"fighters": 80, "torpedos": 12, "name": "Left"},
            "right": {"fighters": 192, "torpedos": 0, "name": "Right"},
        }

        scenario, applied = apply_combat_scenario_overrides(
            payload,
            left={"fighters": 120, "torpedoes": None},
            right={"fighters": 250, "torpedoes": 7},
        )

        self.assertEqual(payload["left"]["fighters"], 80)
        self.assertEqual(payload["right"]["fighters"], 192)
        self.assertEqual(payload["right"]["torpedos"], 0)
        self.assertEqual(scenario["left"]["fighters"], 120)
        self.assertEqual(scenario["left"]["torpedos"], 12)
        self.assertEqual(scenario["right"]["fighters"], 250)
        self.assertEqual(scenario["right"]["torpedos"], 7)
        self.assertEqual(
            applied,
            {
                "left": {"fighters": 120},
                "right": {"fighters": 250, "torpedoes": 7},
            },
        )

    def test_zero_is_a_real_scenario_value(self) -> None:
        payload = {
            "left": {"fighters": 10, "torpedos": 10},
            "right": {"fighters": 10, "torpedos": 10},
        }

        scenario, applied = apply_combat_scenario_overrides(
            payload,
            left={"fighters": 0, "torpedoes": 0},
            right={"fighters": None, "torpedoes": None},
        )

        self.assertEqual(scenario["left"]["fighters"], 0)
        self.assertEqual(scenario["left"]["torpedos"], 0)
        self.assertEqual(applied["left"], {"fighters": 0, "torpedoes": 0})

    def test_missing_side_fails_closed(self) -> None:
        with self.assertRaises(ReplayUnsupported):
            apply_combat_scenario_overrides(
                {"left": {"fighters": 1, "torpedos": 1}},
                left={"fighters": None, "torpedoes": None},
                right={"fighters": 1, "torpedoes": None},
            )


if __name__ == "__main__":
    unittest.main()
