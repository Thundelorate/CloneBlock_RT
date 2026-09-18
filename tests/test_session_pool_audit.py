import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from scripts.audit_session_pool import audit


class SessionPoolAuditTests(unittest.TestCase):
    def write_pool(self, root: Path, overlap: bool) -> Path:
        fields = ["speaker_id", "session_id", "chunk_id", "path", "start_sec",
                  "dur_sec", "source_utter_ids"]
        output = root / "pool.csv"
        rows = []
        for session_index in range(2):
            audio = root / f"session_{session_index}.wav"
            sf.write(audio, np.full(32000, 0.1, dtype=np.float32), 16000)
            sources = ["shared"] if overlap else [f"source_{session_index}"]
            for window in range(2):
                rows.append({"speaker_id": "p1", "session_id": f"s{session_index}",
                             "chunk_id": f"c{session_index}_{window}",
                             "path": audio.relative_to(root).as_posix(), "start_sec": window * 0.5,
                             "dur_sec": 1.0, "source_utter_ids": json.dumps(sources)})
        with output.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return output

    def test_disjoint_sessions_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(audit(self.write_pool(root, False), root, min_windows=2)["ok"])

    def test_source_overlap_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = audit(self.write_pool(root, True), root, min_windows=2)
            self.assertFalse(report["ok"])
            self.assertTrue(any("share" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
