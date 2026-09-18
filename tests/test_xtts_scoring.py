"""Known-answer checks for XTTS speaker-cluster summaries."""

import unittest

from scripts.score_xtts_outputs import cluster_interval


class XttsScoringTests(unittest.TestCase):
    def test_constant_value_has_constant_interval(self):
        rows = [
            {"speaker_id": "a", "value": 0.25},
            {"speaker_id": "a", "value": 0.25},
            {"speaker_id": "b", "value": 0.25},
        ]
        estimate, low, high = cluster_interval(rows, "value", draws=200, seed=42)
        self.assertEqual((estimate, low, high), (0.25, 0.25, 0.25))

    def test_requires_multiple_speakers(self):
        with self.assertRaises(ValueError):
            cluster_interval([{"speaker_id": "a", "value": 1.0}], "value", 20, 42)


if __name__ == "__main__":
    unittest.main()
