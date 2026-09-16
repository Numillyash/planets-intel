import pathlib
import unittest


class TowOrderRuntimeDiagnosticContractTests(unittest.TestCase):
    def test_diagnostic_uses_effective_prediction_and_tow_tower_filter(self) -> None:
        source = pathlib.Path(
            "/app/app/scripts/tow_order_runtime_diagnostic.py"
        ).read_text(encoding="utf-8")

        self.assertIn("movement_prediction_effective", source)
        self.assertIn("get_effective_movement_prediction", source)
        self.assertIn('item.get("tow_tower_ship_id")', source)
        self.assertNotIn('item.get("tower_ship_id")', source)


if __name__ == "__main__":
    unittest.main()
