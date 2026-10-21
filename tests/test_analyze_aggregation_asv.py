import unittest

import numpy as np
import pandas as pd

from scripts.analyze_aggregation_asv import (
    bootstrap_eer_difference,
    bootstrap_eers_from_weights,
    compute_eer,
    paired_bootstrap,
)


class AnalyzeAggregationAsvTest(unittest.TestCase):
    def test_eer_is_zero_for_separated_scores(self):
        labels = np.asarray([True, True, False, False])
        scores = np.asarray([0.9, 0.8, 0.2, 0.1])
        eer, _ = compute_eer(labels, scores)
        self.assertEqual(eer, 0.0)

    def test_eer_is_half_for_identical_distributions(self):
        labels = np.asarray([True, True, False, False])
        scores = np.asarray([0.9, 0.1, 0.9, 0.1])
        eer, _ = compute_eer(labels, scores)
        self.assertAlmostEqual(eer, 0.5)

    def test_paired_bootstrap_uses_shared_speakers(self):
        left = pd.Series({"p1": 0.8, "p2": 0.7, "p3": 0.6})
        right = pd.Series({"p1": 0.3, "p2": 0.2, "p4": 0.1})
        estimate, low, high, count = paired_bootstrap(
            left, right, 200, np.random.default_rng(42)
        )
        self.assertEqual(count, 2)
        self.assertAlmostEqual(estimate, 0.5)
        self.assertLessEqual(low, estimate)
        self.assertGreaterEqual(high, estimate)

    def test_eer_difference_is_paired_by_speaker(self):
        left = pd.DataFrame(
            {
                "speaker": ["p1", "p1", "p2", "p2"],
                "label": ["target", "impostor", "target", "impostor"],
                "score": [0.9, 0.1, 0.8, 0.2],
            }
        )
        right = left.copy()
        estimate, low, high, count = bootstrap_eer_difference(
            left, right, 50, np.random.default_rng(42)
        )
        self.assertEqual(count, 2)
        self.assertEqual(estimate, 0.0)
        self.assertEqual(low, 0.0)
        self.assertEqual(high, 0.0)

    def test_vectorized_eer_bootstrap(self):
        frame = pd.DataFrame(
            {
                "speaker": ["p1", "p1", "p2", "p2"],
                "label": ["target", "impostor", "target", "impostor"],
                "score": [0.9, 0.1, 0.8, 0.2],
            }
        )
        weights = np.asarray([[1, 1], [2, 0], [0, 2]])
        values = bootstrap_eers_from_weights(frame, ["p1", "p2"], weights)
        np.testing.assert_array_equal(values, np.zeros(3))


if __name__ == "__main__":
    unittest.main()
