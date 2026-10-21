import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_aggregation_experiment import audit, audit_trials, load_rows


def valid_manifest():
    return {
        "protocol": {
            "dataset": "VCTK-0.92-mic2",
            "dataset_archive_md5": "8a6ba2946b36fcbef0212cad601f4bfa",
            "dataset_archive_md5_verified": True,
            "seed": 42,
            "k_values": [1, 2, 4, 8, 16],
            "random_repeats": 100,
            "bootstrap_draws": 2000,
            "independent_enrollment": True,
            "non_overlapping_attack_windows": True,
            "same_total_duration_control": True,
            "same_total_duration_control_representation": (
                "single encoder pass over one contiguous K-second waveform"
            ),
            "validation_threshold_frozen_before_test": True,
        },
        "session_pool_sha256": "a" * 64,
        "session_pool_manifest_sha256": "9" * 64,
        "session_pool_source_kind": "official_archive",
        "session_pool_source_archive_md5": "8a6ba2946b36fcbef0212cad601f4bfa",
        "session_pool_source_commit": "4af5c66f",
        "session_pool_source_audit_sha256": "8" * 64,
        "telephony_config_sha256": "f" * 64,
        "checkpoint_sha256": {"reference": "b" * 64, "realistic": "c" * 64},
        "encoder_model_sha256": {"ecapa": "d" * 64, "xvector": "e" * 64},
        "source_file_sha256": {
            "scripts/run_aggregation_advantage_asv.py": "1" * 64,
            "src/metrics/aggregation_protocol.py": "2" * 64,
            "src/models/defense_stftmask.py": "3" * 64,
            "src/transforms/telephony.py": "4" * 64,
        },
        "speakers": ["p1", "p2"],
    }


def complete_rows():
    rows = []
    for encoder in ("ecapa", "xvector"):
        for method in ("none", "reference", "realistic"):
            for speaker, attack in (("p1", "p1_s2"), ("p2", "p2_s2")):
                for strategy in ("random_K", "self_consistency_K", "contiguous_K"):
                    for k in (1, 2, 4, 8, 16):
                        repeats = range(100) if strategy == "random_K" else (0,)
                        for repeat in repeats:
                            indices = list(range(k))
                            selection_id = f"{encoder}:{speaker}:{attack}:{k}:{repeat}"
                            rows.append(
                                {
                                    "method": method,
                                    "encoder": encoder,
                                    "speaker": speaker,
                                    "enrollment_session": f"{speaker}_s1",
                                    "attack_session": attack,
                                    "strategy": strategy,
                                    "representation": (
                                        "single_contiguous_waveform"
                                        if strategy == "contiguous_K"
                                        else "fragment_embedding_mean"
                                    ),
                                    "k": str(k),
                                    "repeat": str(repeat),
                                    "selection_id": selection_id,
                                    "selected_indices": json.dumps(indices),
                                    "selected_intervals": json.dumps(
                                        [[float(index), float(index + 1)] for index in indices]
                                    ),
                                    "selected_duration_sec": str(float(k)),
                                    "selection_span_sec": str(float(k)),
                                    "target_score": "0.6",
                                    "max_impostor_score": "0.2",
                                    "margin": "0.4",
                                }
                            )
    return rows


def complete_trials(rows):
    trials = []
    for row in rows:
        for enrollment_speaker, score in (("p1", "0.6" if row["speaker"] == "p1" else "0.2"),
                                          ("p2", "0.6" if row["speaker"] == "p2" else "0.2")):
            trials.append(
                {
                    "method": row["method"],
                    "encoder": row["encoder"],
                    "speaker": row["speaker"],
                    "enrollment_speaker": enrollment_speaker,
                    "enrollment_session": f"{enrollment_speaker}_s1",
                    "attack_session": row["attack_session"],
                    "strategy": row["strategy"],
                    "representation": row["representation"],
                    "k": row["k"],
                    "repeat": row["repeat"],
                    "selection_id": row["selection_id"],
                    "label": "target" if enrollment_speaker == row["speaker"] else "impostor",
                    "score": score,
                }
            )
    return trials


class AggregationAuditTest(unittest.TestCase):
    def test_complete_protocol_passes(self):
        report = audit(valid_manifest(), complete_rows())
        self.assertTrue(report["ok"], report["errors"])

    def test_enrollment_leakage_fails(self):
        rows = complete_rows()
        rows[0]["enrollment_session"] = rows[0]["attack_session"]
        report = audit(valid_manifest(), rows)
        self.assertFalse(report["ok"])
        self.assertTrue(any("leaks" in error for error in report["errors"]))

    def test_overlapping_selected_intervals_fail(self):
        rows = complete_rows()
        row = next(item for item in rows if item["k"] == "2")
        row["selected_intervals"] = json.dumps([[0.0, 1.0], [0.5, 1.5]])
        report = audit(valid_manifest(), rows)
        self.assertFalse(report["ok"])
        self.assertTrue(any("overlap" in error for error in report["errors"]))

    def test_contiguous_control_requires_single_waveform_encoding(self):
        rows = complete_rows()
        row = next(item for item in rows if item["strategy"] == "contiguous_K")
        row["representation"] = "fragment_embedding_mean"
        report = audit(valid_manifest(), rows)
        self.assertFalse(report["ok"])
        self.assertTrue(any("single waveform" in error for error in report["errors"]))

    def test_k1_control_mismatch_fails(self):
        rows = complete_rows()
        row = next(
            item
            for item in rows
            if item["strategy"] == "contiguous_K"
            and item["k"] == "1"
            and item["method"] == "none"
            and item["encoder"] == "ecapa"
            and item["speaker"] == "p1"
        )
        row["target_score"] = "0.5"
        row["margin"] = "0.3"
        report = audit(valid_manifest(), rows)
        self.assertFalse(report["ok"])
        self.assertTrue(any("scores disagree" in error for error in report["errors"]))

    def test_trial_rows_match_aggregate_scores(self):
        rows = complete_rows()
        errors = audit_trials(valid_manifest(), rows, complete_trials(rows))
        self.assertEqual(errors, [])

    def test_trial_score_mismatch_fails(self):
        rows = complete_rows()
        trials = complete_trials(rows)
        target = next(item for item in trials if item["label"] == "target")
        target["score"] = "0.5"
        errors = audit_trials(valid_manifest(), rows, trials)
        self.assertTrue(any("target score disagrees" in error for error in errors))

    def test_loader_reports_missing_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["method"])
                writer.writeheader()
                writer.writerow({"method": "none"})
            _, errors = load_rows(path)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
