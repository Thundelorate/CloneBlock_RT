import unittest

import numpy as np

from src.metrics.aggregation_protocol import (
    aggregate_embeddings,
    contiguous_self_consistency_indices,
    greedy_non_overlapping_indices,
    random_k_indices,
    score_against_enrollments,
    self_consistency_indices,
    stable_seed,
    threshold_at_far,
)


class AggregationProtocolTest(unittest.TestCase):
    def test_non_overlapping_filter(self):
        selected = greedy_non_overlapping_indices(
            starts=[0.25, 0.0, 1.0, 0.5, 2.0],
            ends=[1.25, 1.0, 2.0, 1.5, 3.0],
        )
        np.testing.assert_array_equal(selected, [1, 2, 4])

    def test_stable_random_draws_are_paired(self):
        first = random_k_indices(range(20), 4, 5, 42, "p225", "s1")
        second = random_k_indices(range(20), 4, 5, 42, "p225", "s1")
        self.assertEqual(stable_seed(42, "p225"), stable_seed(42, "p225"))
        for left, right in zip(first, second):
            np.testing.assert_array_equal(left, right)

    def test_self_consistency_prefers_centroid_aligned_windows(self):
        embeddings = np.asarray([[1, 0], [0.9, 0.1], [-1, 0], [0.8, 0.2]], dtype=float)
        selected = self_consistency_indices(embeddings, 2)
        self.assertNotIn(2, selected)

    def test_contiguous_control_rejects_gaps_and_uses_same_k(self):
        embeddings = np.asarray([[1, 0], [1, 0], [-1, 0], [1, 0]], dtype=float)
        selected = contiguous_self_consistency_indices(
            embeddings,
            starts=[0, 1, 3, 4],
            ends=[1, 2, 4, 5],
            k=2,
        )
        np.testing.assert_array_equal(selected, [0, 1])
        self.assertEqual(len(selected), 2)

    def test_independent_enrollment_scores(self):
        attack = aggregate_embeddings(np.asarray([[1, 0], [0.8, 0.2]]), [0, 1])
        result = score_against_enrollments(
            attack,
            "target",
            {"target": np.asarray([1, 0]), "other": np.asarray([0, 1])},
        )
        self.assertGreater(result["target_score"], result["max_impostor_score"])
        self.assertAlmostEqual(
            result["margin"], result["target_score"] - result["max_impostor_score"]
        )

    def test_far_threshold(self):
        threshold = threshold_at_far([0.1, 0.2, 0.3, 0.4], target_far=0.25)
        self.assertEqual(sum(score >= threshold for score in [0.1, 0.2, 0.3, 0.4]), 1)


if __name__ == "__main__":
    unittest.main()
