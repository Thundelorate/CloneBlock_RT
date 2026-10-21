import unittest

from scripts.analyze_aggregation_advantage import summarize


class AggregationAdvantageTest(unittest.TestCase):
    def test_expected_contrasts(self):
        rows = []
        for method, offset in (("baseline", 0.0), ("defense", -0.1)):
            for speaker in ("a", "b"):
                session = f"{speaker}_s0"
                for strategy, selection_gain in (("random_K", 0.0), ("bestK_by_self_consistency", 0.05)):
                    for k, aggregation_gain in ((1, 0.0), (2, 0.2)):
                        rows.append(
                            {
                                "method": method,
                                "speaker_id": speaker,
                                "session_id": session,
                                "path": f"{session}.wav",
                                "strategy": strategy,
                                "K": str(k),
                                "cos": str(0.5 + offset + selection_gain + aggregation_gain),
                            }
                        )
        result = summarize(rows, draws=100, seed=7)
        key = {(row["method"], row["contrast"], row["strategy"], row["K"]): row for row in result}
        self.assertAlmostEqual(
            key[("baseline", "aggregation_gain_vs_k1", "random_K", 2)]["estimate"], 0.2
        )
        self.assertAlmostEqual(
            key[("baseline", "selection_gain_vs_random", "bestK_by_self_consistency", 2)]["estimate"], 0.05
        )

    def test_rejects_incomplete_grid(self):
        rows = [
            {"method": "baseline", "speaker_id": "a", "session_id": "s", "path": "s.wav",
             "strategy": "random_K", "K": "1", "cos": "0.5"},
            {"method": "baseline", "speaker_id": "a", "session_id": "s", "path": "s.wav",
             "strategy": "bestK_by_self_consistency", "K": "1", "cos": "0.6"},
            {"method": "baseline", "speaker_id": "b", "session_id": "t", "path": "t.wav",
             "strategy": "random_K", "K": "1", "cos": "0.5"},
        ]
        with self.assertRaises(ValueError):
            summarize(rows, draws=10)


if __name__ == "__main__":
    unittest.main()
