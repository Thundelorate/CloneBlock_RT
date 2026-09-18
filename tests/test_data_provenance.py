"""Exercise actual crop writing, speaker isolation, and corrupt-manifest detection."""

import csv
import json
import random
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from scripts.audit_experiment_data import audit, sha256_file
from scripts.prepare_data import MANIFEST_FIELDS, discover_vctk, slice_speaker_segments


class DataProvenanceTests(unittest.TestCase):
    def test_microphone_selection_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "VCTK-Corpus-0.92/wav48_silence_trimmed/p225"
            folder.mkdir(parents=True)
            for mic in ("mic1", "mic2"):
                (folder / f"p225_001_{mic}.flac").touch()
            self.assertEqual([p.name for _, p in discover_vctk(root)], ["p225_001_mic2.flac"])
            self.assertEqual([p.name for _, p in discover_vctk(root, "mic1")], ["p225_001_mic1.flac"])

    def test_crop_roundtrip_and_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, processed, splits = root / "raw", root / "wav", root / "splits"
            raw.mkdir()
            splits.mkdir()
            for split, speaker in zip(("train", "val", "test"), ("a", "b", "c")):
                source = raw / (speaker + ".wav")
                waveform = np.random.default_rng(4).uniform(-0.2, 0.2, 64000).astype(np.float32)
                sf.write(source, waveform, 16000, subtype="PCM_16")
                rows = slice_speaker_segments(speaker, [source], processed, 2, 2, 2, 16000,
                                              random.Random(5), raw_dir=raw)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["source_utter_id"], speaker)
                self.assertEqual(rows[0]["is_full_utterance"], 0)
                original, _ = sf.read(source)
                crop, _ = sf.read(processed / rows[0]["path"])
                np.testing.assert_array_equal(crop, original[rows[0]["source_start_sample"]:rows[0]["source_end_sample"]])
                with (splits / f"{split}.csv").open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
                    writer.writeheader()
                    writer.writerows(rows)
            metadata = {"split_sha256": {s: sha256_file(splits / f"{s}.csv") for s in ("train", "val", "test")}}
            (splits / "preparation.json").write_text(json.dumps(metadata), encoding="utf-8")
            self.assertTrue(audit(splits, processed, raw)["ok"])
            (splits / "test.csv").write_bytes((splits / "train.csv").read_bytes())
            report = audit(splits, processed, raw)
            self.assertFalse(report["ok"])
            self.assertTrue(any("leaks across splits" in error for error in report["errors"]))
            self.assertTrue(any("manifest changed" in error for error in report["errors"]))

    def test_invalid_crop_durations_fail_before_io(self):
        with self.assertRaises(ValueError):
            slice_speaker_segments("a", [], Path("unused"), 2, 0, 2, 16000, random.Random(1))


if __name__ == "__main__":
    unittest.main()
