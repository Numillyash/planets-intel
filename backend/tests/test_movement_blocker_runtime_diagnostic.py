import unittest

from app.scripts.movement_blocker_runtime_diagnostic import (
    summarize_prediction_items,
)


class MovementBlockerRuntimeDiagnosticTests(unittest.TestCase):
    def test_summarize_keeps_predicted_and_unknown_separate(self) -> None:
        result = summarize_prediction_items(
            [
                {
                    "phase": "move_most",
                    "status": "moved",
                    "fuel_status": "sufficient",
                    "certain": True,
                    "predicted_x": 10.0,
                    "predicted_y": 20.0,
                    "blocker_class": None,
                },
                {
                    "phase": "intercept",
                    "status": "unresolved_post_move",
                    "fuel_status": "unresolved_intercept",
                    "certain": False,
                    "predicted_x": None,
                    "predicted_y": None,
                    "blocker_class": "phase_state_required",
                },
            ]
        )

        self.assertEqual(
            result["summary"],
            {
                "prediction_items": 2,
                "predicted_items": 1,
                "unknown_items": 1,
            },
        )
        self.assertEqual(
            result["blocker_counts"],
            {"phase_state_required": 1},
        )
        self.assertEqual(
            result["blocker_phase_counts"],
            {"phase_state_required": {"intercept": 1}},
        )

    def test_summarize_splits_tow_roles(self) -> None:
        result = summarize_prediction_items(
            [
                {
                    "phase": "tow",
                    "tow_role": "tower",
                    "status": "unknown",
                    "fuel_status": "unknown",
                    "certain": False,
                    "predicted_x": None,
                    "predicted_y": None,
                    "blocker_class": "dependency_unresolved",
                },
                {
                    "phase": "tow",
                    "tow_role": "target",
                    "status": "unknown",
                    "fuel_status": "unknown",
                    "certain": False,
                    "predicted_x": None,
                    "predicted_y": None,
                    "blocker_class": "dependency_unresolved",
                },
            ]
        )

        self.assertEqual(
            result["phase_counts"],
            {"tow:target": 1, "tow:tower": 1},
        )
        self.assertEqual(
            result["blocker_phase_counts"],
            {
                "dependency_unresolved": {
                    "tow:target": 1,
                    "tow:tower": 1,
                }
            },
        )

    def test_uncertain_row_without_blocker_is_visible(self) -> None:
        result = summarize_prediction_items(
            [
                {
                    "phase": "move_most",
                    "status": "unknown",
                    "fuel_status": "unknown",
                    "certain": False,
                    "predicted_x": None,
                    "predicted_y": None,
                    "blocker_class": None,
                }
            ]
        )

        self.assertEqual(
            result["blocker_counts"],
            {"unclassified_unknown": 1},
        )


if __name__ == "__main__":
    unittest.main()
