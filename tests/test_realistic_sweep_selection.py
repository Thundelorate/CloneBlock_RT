import csv
import tempfile
import unittest
from pathlib import Path

from scripts.select_realistic_sweep import budget_rows, security_rows


class RealisticSweepSelectionTests(unittest.TestCase):
    def test_security_reader_keeps_only_realistic_strategy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "security.csv"
            fields = ["method", "strategy", "K16_mean", "AUCK"]
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({"method": "realistic_a0p18", "strategy": "bestK_by_self_consistency",
                                 "K16_mean": 0.7, "AUCK": 0.6})
                writer.writerow({"method": "realistic_a0p18", "strategy": "bestK_by_clean_consistency",
                                 "K16_mean": 0.9, "AUCK": 0.8})
            rows = security_rows([path])
            self.assertEqual(float(rows["realistic_a0p18"]["K16_mean"]), 0.7)

    def test_budget_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "budget.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["method", "relative_l2_mean"])
                writer.writeheader()
                writer.writerow({"method": "realistic_a0p12", "relative_l2_mean": 0.1})
            self.assertIn("realistic_a0p12", budget_rows(path))


if __name__ == "__main__":
    unittest.main()
