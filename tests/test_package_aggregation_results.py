import json
import tempfile
import unittest
from pathlib import Path

from scripts.package_aggregation_results import REQUIRED_FILES, build_bundle


class PackageAggregationResultsTest(unittest.TestCase):
    def test_bundle_contains_integrity_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            for relative in REQUIRED_FILES:
                path = repo / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if relative.endswith("aggregation_asv_test_audit.json"):
                    path.write_text(json.dumps({"ok": True}), encoding="utf-8")
                else:
                    path.write_text(f"fixture for {relative}\n", encoding="utf-8")
            output = repo / "artifacts/bundles/results.tar.gz"
            report = build_bundle(repo, output, max_bytes=1024 * 1024)
            self.assertTrue(report["ok"])
            self.assertTrue(output.is_file())
            self.assertTrue(output.with_suffix(".gz.sha256").is_file())
            recovery = json.loads(
                (repo / "artifacts/recovery/aggregation_advantage_files.json").read_text()
            )
            self.assertEqual(len(recovery["files"]), len(REQUIRED_FILES))

    def test_failed_audit_is_not_packaged(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            for relative in REQUIRED_FILES:
                path = repo / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps({"ok": False})
                    if relative.endswith("aggregation_asv_test_audit.json")
                    else "fixture\n",
                    encoding="utf-8",
                )
            with self.assertRaises(RuntimeError):
                build_bundle(repo, repo / "bundle.tar.gz", max_bytes=1024 * 1024)


if __name__ == "__main__":
    unittest.main()
