"""Known-answer checks for speaker-cluster quality intervals."""

import unittest

from scripts.bootstrap_quality_ci import interval


class QualityBootstrapTests(unittest.TestCase):
    def test_constant_metric_has_constant_interval(self):
        rows = [
            {"speaker_id": "a", "metric": "0.2"},
            {"speaker_id": "a", "metric": "0.2"},
            {"speaker_id": "b", "metric": "0.2"},
        ]
        for value in interval(rows, "metric", draws=200, seed=42):
            self.assertAlmostEqual(value, 0.2)

    def test_requires_multiple_speakers(self):
        with self.assertRaises(ValueError):
            interval([{"speaker_id": "a", "metric": "0.2"}], "metric", draws=20, seed=42)


if __name__ == "__main__":
    unittest.main()
