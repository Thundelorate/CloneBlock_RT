"""Checks for score-independent XTTS sampling and validation thresholding."""

import unittest

from scripts.build_xtts_manifest import build_manifest
from scripts.calibrate_asv_threshold import calibrate


class XttsProtocolTests(unittest.TestCase):
    def test_manifest_is_deterministic_stratified_and_disjoint(self):
        rows = []
        for speaker in ("a", "b", "c"):
            for session in range(3):
                rows.append({
                    "speaker_id": speaker,
                    "session_id": f"{speaker}_{session}",
                    "path": f"{speaker}/{session}.wav",
                })
        first = build_manifest(rows, n_sessions=5, seed=42)
        second = build_manifest(list(reversed(rows)), n_sessions=5, seed=42)
        self.assertEqual(first, second)
        self.assertEqual({row["speaker_id"] for row in first[:3]}, {"a", "b", "c"})
        self.assertTrue(all(row["attack_session_id"] != row["enrollment_session_id"] for row in first))

    def test_manifest_rejects_single_session_speaker(self):
        with self.assertRaises(ValueError):
            build_manifest([{"speaker_id": "a", "session_id": "one", "path": "a.wav"}], 1, 42)

    def test_threshold_respects_discrete_far(self):
        rows = []
        for score in (0.9, 0.8):
            rows.append({"method": "no_defense", "label": "target", "score": str(score)})
        for score in (0.1, 0.2, 0.3, 0.4):
            rows.append({"method": "no_defense", "label": "impostor", "score": str(score)})
        result = calibrate(rows, "no_defense", target_far=0.25)
        self.assertEqual(result["threshold"], 0.4)
        self.assertEqual(result["achieved_far"], 0.25)
        self.assertEqual(result["target_accept_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
