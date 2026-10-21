import unittest

import pandas as pd

from scripts.summarize_aggregation_claim import build_decision


def row(contrast, strategy, estimate, low, high):
    return {
        "contrast": contrast,
        "method": "none",
        "encoder": "ecapa",
        "strategy": strategy,
        "k": 16,
        "metric": "target_score",
        "estimate": estimate,
        "ci_low": low,
        "ci_high": high,
        "speakers": 11,
    }


class SummarizeAggregationClaimTest(unittest.TestCase):
    def frame(self, primary_low):
        return pd.DataFrame(
            [
                row("aggregation_gain_vs_k1", "random_K", 0.08, primary_low, 0.12),
                row(
                    "aggregation_gain_vs_k1",
                    "self_consistency_K",
                    0.10,
                    0.05,
                    0.15,
                ),
                row(
                    "fragmentation_gain_selfcons_vs_contiguous",
                    "self_consistency_K-contiguous_K",
                    0.03,
                    0.01,
                    0.05,
                ),
            ]
        )

    def test_primary_claim_requires_positive_lower_ci_bound(self):
        self.assertTrue(build_decision(self.frame(0.02))["primary_claim"]["supported"])
        self.assertFalse(build_decision(self.frame(-0.01))["primary_claim"]["supported"])

    def test_secondary_result_cannot_override_primary_rule(self):
        result = build_decision(self.frame(-0.01))
        self.assertFalse(result["primary_claim"]["supported"])
        self.assertGreater(
            result["secondary_evidence"][
                "self_consistency_k16_vs_contiguous_k16_target_similarity"
            ]["estimate"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
