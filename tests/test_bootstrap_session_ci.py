"""Known-answer checks for clustered confidence intervals."""

import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
from scripts.bootstrap_session_ci import load_runs, summarize


def fixture():
    rows = []
    for speaker, count, value in [("a", 1, 0.2), ("b", 3, 0.8), ("c", 2, 0.5)]:
        for session in range(count):
            for method, delta in [("baseline", 0.0), ("defense", -0.125)]:
                for k in (1, 2, 16):
                    rows.append(dict(method=method, speaker_id=speaker, session_id=str(session),
                                     path=f"{speaker}/{session}.wav", strategy="bestK_by_self_consistency",
                                     attacker_view="realistic", selection_source="tele_defended",
                                     K=str(k), cos=str(value + delta), candidate_count="64", seed="42",
                                     selected_indices="[]"))
    return rows


class BootstrapTests(unittest.TestCase):
    def test_constant_paired_effect_has_constant_interval(self):
        for row in summarize(fixture(), ks=(1, 2, 16), draws=500):
            if row["kind"] == "paired_delta":
                expected = 0.0 if row["metric"] == "slope_16_1" else -0.125
                for field in ("estimate", "ci_low", "ci_high"):
                    self.assertAlmostEqual(row[field], expected)

    def test_unequal_session_counts_match_cluster_resampling(self):
        output = summarize(fixture(), ks=(1, 2, 16), draws=500, seed=8)
        row = next(r for r in output if r["method"] == "baseline" and r["metric"] == "AUCK")
        samples = np.random.default_rng(8).integers(0, 3, size=(500, 3))
        totals, counts = np.array([0.2, 2.4, 1.0]), np.array([1, 3, 2])
        expected = totals[samples].sum(axis=1) / counts[samples].sum(axis=1)
        self.assertAlmostEqual(row["estimate"], 3.6 / 6)
        self.assertAlmostEqual(row["ci_low"], np.quantile(expected, 0.025))
        self.assertAlmostEqual(row["ci_high"], np.quantile(expected, 0.975))
        self.assertEqual(row["n_speakers"], 3)

    def test_order_invariance(self):
        rows = fixture()
        self.assertEqual(summarize(rows, ks=(1, 2, 16)), summarize(list(reversed(rows)), ks=(1, 2, 16)))

    def test_invalid_pairing_fails(self):
        for change in ("missing", "duplicate", "nonfinite", "candidate", "seed", "protocol"):
            with self.subTest(change=change):
                rows = copy.deepcopy(fixture())
                if change == "missing":
                    rows.pop()
                elif change == "duplicate":
                    rows.append(rows[0])
                elif change == "nonfinite":
                    rows[0]["cos"] = "nan"
                elif change == "candidate":
                    rows[0]["candidate_count"] = "63"
                elif change == "seed":
                    rows[0]["seed"] = "9"
                else:
                    rows[0]["selection_source"] = "defended"
                with self.assertRaises(ValueError):
                    summarize(rows, ks=(1, 2, 16))

    def test_no_single_speaker_interval(self):
        with self.assertRaises(ValueError):
            summarize([r for r in fixture() if r["speaker_id"] == "a"], ks=(1, 2, 16))

    def test_random_draw_mismatch_fails(self):
        rows = fixture()
        for row in rows:
            row["strategy"] = "random_K"
            row["selection_source"] = "none"
        rows[0]["selected_indices"] = "[3]"
        with self.assertRaises(ValueError):
            summarize(rows, ks=(1, 2, 16))

    def test_cli_and_metadata_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            metadata = dict(protocol_version="realistic_v1", k_list=[1, 2, 16], seed=42,
                            speaker_encoder_name="synthetic_test", telephony_codec="none",
                            telephony_codec_bitrate="16k", session_pool_sha256="test_pool",
                            eval_config_sha256="test_eval", telephony_config_sha256="test_phone",
                            selection_protocols={"bestK_by_self_consistency": {
                                "attacker_view": "realistic", "selection_source": "tele_defended"}})
            for method in ("baseline", "defense"):
                path = root / f"session_attack_eval_{method}.json"
                path.write_text(json.dumps({"method": method, "metadata": metadata}), encoding="utf-8")
                paths.append(path)
                rows = [r for r in fixture() if r["method"] == method]
                with (root / f"session_attack_per_session_{method}.csv").open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
            script = Path(__file__).resolve().parents[1] / "scripts/bootstrap_session_ci.py"
            result = subprocess.run([sys.executable, "-B", str(script), "--runs", *map(str, paths),
                                     "--draws", "100", "--output", str(root / "ci.csv")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((root / "ci.json").read_text(encoding="utf-8"))
            self.assertEqual(report["bootstrap"]["unit"], "speaker")
            self.assertEqual(len(report["inputs"]), 2)
            metadata["telephony_codec"] = "opus"
            paths[1].write_text(json.dumps({"method": "defense", "metadata": metadata}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "metadata differ"):
                load_runs(paths)


if __name__ == "__main__":
    unittest.main()
