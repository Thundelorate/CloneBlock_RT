import csv
from pathlib import Path
import tempfile
import unittest

import torch

from scripts.check_training_run import check_run


class TrainingRunCheckTests(unittest.TestCase):
    def fixture(self, root, loss=1.0, weight=0.5):
        (root / "artifacts/tables").mkdir(parents=True)
        (root / "checkpoints/defense").mkdir(parents=True)
        row = dict(step=1, loss_total=loss, loss_spk_global=0.9, loss_rec=0.1,
                   loss_energy=0.01, val_speaker_sim_tel=0.8)
        with (root / "artifacts/tables/train_test_curve.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        torch.save({"model_state_dict": {"weight": torch.tensor([weight])},
                    "run_name": "test", "dataset": "fixture", "step": 1,
                    "best_val_speaker_sim_tel": 0.8}, root / "checkpoints/defense/test_best.pt")

    def test_complete_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            self.assertTrue(check_run(root, "test", 1)["ok"])

    def test_incomplete_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            with self.assertRaisesRegex(ValueError, "incomplete"):
                check_run(root, "test", 2)

    def test_nonfinite_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, loss=float("nan"))
            with self.assertRaisesRegex(ValueError, "Non-finite"):
                check_run(root, "test", 1)

    def test_nonfinite_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, weight=float("inf"))
            with self.assertRaisesRegex(ValueError, "non-finite checkpoint"):
                check_run(root, "test", 1)


if __name__ == "__main__":
    unittest.main()
