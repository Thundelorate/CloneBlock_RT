import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from scripts.run_aggregation_advantage_asv import (
    checkpoint_state,
    concatenate_selected_windows,
    load_sessions,
    load_defense,
    load_embedding_cache,
    save_embedding_cache,
    selection_identifier,
    transform_queries,
)


class IdentityTelephony:
    def __call__(self, signal, sample_rate):
        self.sample_rate = sample_rate
        return signal


class AggregationAsvRunnerTest(unittest.TestCase):
    def test_session_loader_removes_overlaps_and_crops(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wav = root / "session.wav"
            sample_rate = 16000
            signal = np.linspace(-0.2, 0.2, 4 * sample_rate, dtype=np.float32)
            sf.write(wav, signal, sample_rate)
            pool = root / "pool.csv"
            fields = ["speaker_id", "session_id", "audio_path", "window_start", "window_end"]
            with pool.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for session in ("s1", "s2", "s3"):
                    for start in (0.0, 0.25, 1.0, 1.25, 2.0, 3.0):
                        writer.writerow(
                            {
                                "speaker_id": "p1",
                                "session_id": session,
                                "audio_path": str(wav),
                                "window_start": start,
                                "window_end": start + 1.0,
                            }
                        )
            sessions = load_sessions(pool, sample_rate, window_sec=1.0, min_windows=4)
            self.assertEqual(len(sessions), 3)
            for session in sessions.values():
                self.assertEqual(session.waveforms.shape, (4, sample_rate))
                np.testing.assert_allclose(session.starts, [0.0, 1.0, 2.0, 3.0])

    def test_checkpoint_state_unwraps_common_payload(self):
        state = {"weight": torch.ones(2)}
        self.assertIs(checkpoint_state({"model_state_dict": state}), state)
        self.assertIs(checkpoint_state({"model": {"state_dict": state}}), state)

    def test_defense_loader_accepts_module_prefix(self):
        from src.models.defense_stftmask import STFTMaskDefense

        with tempfile.TemporaryDirectory() as directory:
            model = STFTMaskDefense()
            prefixed = {f"module.{key}": value for key, value in model.state_dict().items()}
            path = Path(directory) / "checkpoint.pt"
            torch.save({"model_state_dict": prefixed}, path)
            restored = load_defense(path, torch.device("cpu"))
            self.assertIsNotNone(restored)

    def test_identity_query_transform_preserves_shape(self):
        waveforms = np.ones((3, 16000), dtype=np.float32) * 0.1
        telephony = IdentityTelephony()
        output = transform_queries(
            waveforms,
            defense=None,
            telephony=telephony,
            sample_rate=16000,
            device=torch.device("cpu"),
        )
        np.testing.assert_array_equal(output, waveforms)
        self.assertEqual(telephony.sample_rate, 16000)

    def test_selection_identifier_is_stable(self):
        first = selection_identifier("p1", "s2", 16, [1, 2, 3])
        second = selection_identifier("p1", "s2", 16, [1, 2, 3])
        different = selection_identifier("p1", "s2", 8, [1, 2, 3])
        self.assertEqual(first, second)
        self.assertNotEqual(first, different)

    def test_contiguous_control_concatenates_once_in_order(self):
        waveforms = np.asarray([[1, 2], [3, 4], [5, 6]], dtype=np.float32)
        combined = concatenate_selected_windows(waveforms, np.asarray([1, 2]))
        np.testing.assert_array_equal(combined, [[3, 4, 5, 6]])
        with self.assertRaises(ValueError):
            concatenate_selected_windows(waveforms, np.asarray([0, 2]))

    def test_embedding_cache_checks_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.npz"
            embeddings = np.arange(12, dtype=float).reshape(3, 4)
            save_embedding_cache(path, "correct", embeddings)
            restored = load_embedding_cache(path, "correct", expected_rows=3)
            np.testing.assert_array_equal(restored, embeddings)
            self.assertIsNone(load_embedding_cache(path, "wrong", expected_rows=3))
            self.assertIsNone(load_embedding_cache(path, "correct", expected_rows=2))


if __name__ == "__main__":
    unittest.main()
