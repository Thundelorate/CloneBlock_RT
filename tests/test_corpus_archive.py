"""Exercise archive verification and fail-closed extraction on tiny fixtures."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts.verify_extract_corpus import checked_path, main


class CorpusArchiveTests(unittest.TestCase):
    def run_fixture(self, root, dataset, archive, **overrides):
        spec = {
            "archive": archive.name,
            "size": archive.stat().st_size,
            "md5": hashlib.md5(archive.read_bytes()).hexdigest(),
            "directory": "VCTK-Corpus-0.92" if dataset == "vctk" else "LibriSpeech",
            "source": "test fixture",
            **overrides,
        }
        with patch("scripts.verify_extract_corpus.CORPORA", {dataset: spec}), patch(
            "sys.argv", ["verify", "--dataset", dataset, "--raw_dir", str(root),
                         "--report_dir", str(root / "audit")]
        ):
            main()

    def test_verified_zip_and_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "data.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("txt/p225/a.txt", "A genuine-shaped test path.")
            self.run_fixture(root, "vctk", archive)
            self.run_fixture(root, "vctk", archive)
            self.assertTrue((root / "VCTK-Corpus-0.92/txt/p225/a.txt").is_file())
            self.assertTrue(json.loads((root / "audit/vctk_archive.json").read_text())["verified"])

    def test_bad_checksum_does_not_extract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "data.zip"
            archive.write_bytes(b"not an archive")
            with self.assertRaisesRegex(ValueError, "MD5 mismatch"):
                self.run_fixture(root, "vctk", archive, md5="0" * 32)
            self.assertFalse((root / "VCTK-Corpus-0.92").exists())

    def test_zip_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "data.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("../escaped.txt", "unsafe")
            with self.assertRaisesRegex(ValueError, "Unsafe archive member"):
                self.run_fixture(root, "vctk", archive)
            self.assertFalse((root / "escaped.txt").exists())

    def test_tar_root_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "data.tar.gz"
            with tarfile.open(archive, "w:gz") as handle:
                entry = tarfile.TarInfo("LibriSpeech/dev-clean/test.txt")
                entry.size = 4
                handle.addfile(entry, io.BytesIO(b"test"))
            self.run_fixture(root, "librispeech", archive)
            self.assertEqual((root / "LibriSpeech/dev-clean/test.txt").read_text(), "test")

    def test_absolute_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                checked_path(root / "extract", str(root / "outside"))


if __name__ == "__main__":
    unittest.main()
