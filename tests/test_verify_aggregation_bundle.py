import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.package_aggregation_results import REQUIRED_FILES, build_bundle
from scripts.verify_aggregation_bundle import verify_bundle


def make_fixture(repo: Path) -> Path:
    for relative in REQUIRED_FILES:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"ok": True})
            if relative.endswith("aggregation_asv_test_audit.json")
            else f"fixture for {relative}\n",
            encoding="utf-8",
        )
    bundle = repo / "artifacts/bundles/results.tar.gz"
    build_bundle(repo, bundle, max_bytes=1024 * 1024)
    return bundle


class VerifyAggregationBundleTest(unittest.TestCase):
    def test_verify_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = make_fixture(root / "source")
            destination = root / "restored"
            report = verify_bundle(bundle, destination, overwrite=False)
            self.assertTrue(report["ok"])
            self.assertEqual(report["verified_files"], len(REQUIRED_FILES))
            self.assertTrue((destination / REQUIRED_FILES[0]).is_file())

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "unsafe.tar.gz"
            payload = Path(directory) / "payload"
            payload.write_text("unsafe", encoding="utf-8")
            with tarfile.open(bundle, "w:gz") as archive:
                archive.add(payload, arcname="../outside")
            with self.assertRaises(ValueError):
                verify_bundle(bundle, None, overwrite=False)

    def test_refuses_different_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = make_fixture(root / "source")
            destination = root / "restored"
            conflict = destination / REQUIRED_FILES[0]
            conflict.parent.mkdir(parents=True, exist_ok=True)
            conflict.write_text("different", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                verify_bundle(bundle, destination, overwrite=False)


if __name__ == "__main__":
    unittest.main()
