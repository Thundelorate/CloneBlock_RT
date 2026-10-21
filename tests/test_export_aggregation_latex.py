import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.export_aggregation_latex import (
    write_contrast_table,
    write_defense_table,
    write_fragmentation_table,
    write_strength_table,
)


def fixtures():
    summary_rows = []
    contrast_rows = []
    for method in ("none", "reference", "realistic"):
        for encoder in ("ecapa", "xvector"):
            for strategy in ("random_K", "self_consistency_K", "contiguous_K"):
                for k in (1, 2, 4, 8, 16):
                    for metric in ("target_score", "margin", "eer", "acceptance"):
                        summary_rows.append(
                            {
                                "method": method,
                                "encoder": encoder,
                                "strategy": strategy,
                                "k": k,
                                "metric": metric,
                                "estimate": 0.5,
                                "ci_low": 0.4,
                                "ci_high": 0.6,
                            }
                        )
                    for name, metric in (
                        ("aggregation_gain_vs_k1", "target_score"),
                        ("aggregation_gain_vs_k1", "margin"),
                        ("eer_change_vs_k1", "eer"),
                    ):
                        contrast_rows.append(
                            {
                                "contrast": name,
                                "method": method,
                                "encoder": encoder,
                                "strategy": strategy,
                                "k": k,
                                "metric": metric,
                                "estimate": 0.1,
                                "ci_low": 0.05,
                                "ci_high": 0.15,
                            }
                        )
            for metric in ("target_score", "margin"):
                contrast_rows.append(
                    {
                        "contrast": "fragmentation_gain_selfcons_vs_contiguous",
                        "method": method,
                        "encoder": encoder,
                        "strategy": "self_consistency_K-contiguous_K",
                        "k": 16,
                        "metric": metric,
                        "estimate": 0.1,
                        "ci_low": 0.05,
                        "ci_high": 0.15,
                    }
                )
            contrast_rows.append(
                {
                    "contrast": "eer_change_selfcons_vs_contiguous",
                    "method": method,
                    "encoder": encoder,
                    "strategy": "self_consistency_K-contiguous_K",
                    "k": 16,
                    "metric": "eer",
                    "estimate": -0.1,
                    "ci_low": -0.15,
                    "ci_high": -0.05,
                }
            )
    return pd.DataFrame(summary_rows), pd.DataFrame(contrast_rows)


class ExportAggregationLatexTest(unittest.TestCase):
    def test_all_tables_are_written(self):
        summary, contrasts = fixtures()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            strength = root / "strength.tex"
            defense = root / "defense.tex"
            contrast = root / "contrast.tex"
            fragmentation = root / "fragmentation.tex"
            write_strength_table(summary, strength)
            write_defense_table(summary, defense)
            write_contrast_table(contrasts, contrast)
            write_fragmentation_table(contrasts, fragmentation)
            for path in (strength, defense, contrast, fragmentation):
                text = path.read_text(encoding="utf-8")
                self.assertIn(r"\begin{tabular}", text)
                self.assertIn(r"\bottomrule", text)


if __name__ == "__main__":
    unittest.main()
