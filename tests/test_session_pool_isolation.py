import csv
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf

from scripts import build_session_pool_v3 as builder


class SessionPoolIsolationTests(unittest.TestCase):
    def test_dataset_outputs_do_not_replace_legacy_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            splits = root / "data/splits/librispeech"
            wavs = root / "data/processed/librispeech/wav16k"
            splits.mkdir(parents=True)
            wavs.mkdir(parents=True)
            legacy = root / "data/splits/session_pool_v3_val.csv"
            legacy.write_text("existing VCTK output")
            for split in ("train", "val", "test"):
                sf.write(wavs / f"{split}.wav", np.full(48000, 0.2), 16000)
                with (splits / f"{split}.csv").open("w", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["speaker_id", "path"])
                    writer.writeheader()
                    writer.writerow({"speaker_id": split, "path": f"{split}.wav"})
            args = SimpleNamespace(dataset="librispeech", seed=42, isolate_dataset=True,
                                   sessions_per_speaker=1, max_build_tries=1,
                                   target_session_sec=2, min_gap_sec=0, max_gap_sec=0,
                                   window_sec=1, hop_sec=0.25, rms_thr=0.008,
                                   min_windows_per_session=2)
            with patch.object(builder, "REPO_ROOT", root), patch.object(builder, "parse_args", return_value=args):
                builder.main()
            self.assertEqual(legacy.read_text(), "existing VCTK output")
            with (splits / "session_pool_v3_val.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertTrue(rows)
            for row in rows:
                self.assertIn("librispeech", Path(row["path"]).parts)
                self.assertTrue((root / row["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
