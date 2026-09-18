#!/usr/bin/env python3
"""Verify the frozen paper evidence and trained defense checkpoints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = (
    ROOT / "artifacts/tables/paper_icassp/evidence_manifest.json",
    ROOT / "artifacts/audit/defense_checkpoint_manifest_20260919.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_files(manifest: dict) -> dict[str, dict]:
    if "files" in manifest:
        return manifest["files"]
    merged = {}
    merged.update(manifest.get("sources", {}))
    merged.update(manifest.get("outputs", {}))
    return merged


def main() -> int:
    failures = []
    checked = 0
    for manifest_path in MANIFESTS:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for relative, expected in expected_files(manifest).items():
            path = ROOT / relative
            checked += 1
            if not path.is_file():
                failures.append(f"missing: {relative}")
                continue
            size = path.stat().st_size
            if size != expected["size_bytes"]:
                failures.append(
                    f"size mismatch: {relative} ({size} != {expected['size_bytes']})"
                )
                continue
            actual = sha256(path)
            if actual != expected["sha256"]:
                failures.append(f"sha256 mismatch: {relative}")
    if failures:
        print("SNAPSHOT_VERIFY_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"SNAPSHOT_VERIFY_OK files={checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
