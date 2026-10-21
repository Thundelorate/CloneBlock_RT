#!/usr/bin/env python3
"""Create an integrity-checked, GitHub-sized aggregation experiment bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_FILES = (
    "artifacts/audit/vctk_aggregation_official_source.json",
    "data/splits/vctk/aggregation_session_pool_manifest.json",
    "data/splits/vctk/session_pool_aggregation_validation.csv",
    "data/splits/vctk/session_pool_aggregation_validation_sources.csv",
    "data/splits/vctk/session_pool_aggregation_test.csv",
    "data/splits/vctk/session_pool_aggregation_test_sources.csv",
    "artifacts/experiments/aggregation_advantage/aggregation_asv_validation_aggregates.csv",
    "artifacts/experiments/aggregation_advantage/aggregation_asv_validation_trials.csv",
    "artifacts/experiments/aggregation_advantage/aggregation_asv_validation_thresholds.json",
    "artifacts/experiments/aggregation_advantage/aggregation_asv_validation_manifest.json",
    "artifacts/experiments/aggregation_advantage/aggregation_asv_test_aggregates.csv",
    "artifacts/experiments/aggregation_advantage/aggregation_asv_test_trials.csv",
    "artifacts/experiments/aggregation_advantage/aggregation_asv_test_thresholds.json",
    "artifacts/experiments/aggregation_advantage/aggregation_asv_test_manifest.json",
    "artifacts/tables/paper_icassp/aggregation_asv_summary.csv",
    "artifacts/tables/paper_icassp/aggregation_asv_summary.json",
    "artifacts/tables/paper_icassp/aggregation_asv_contrasts.csv",
    "artifacts/tables/paper_icassp/aggregation_attack_strength.tex",
    "artifacts/tables/paper_icassp/aggregation_defense_comparison.tex",
    "artifacts/tables/paper_icassp/aggregation_contrasts.tex",
    "artifacts/tables/paper_icassp/aggregation_fragmentation_control.tex",
    "artifacts/tables/paper_icassp/aggregation_claim_decision.json",
    "artifacts/figures/aggregation_asv_curves.png",
    "artifacts/figures/aggregation_asv_curves.pdf",
    "artifacts/audit/aggregation_asv_test_audit.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_value(repo: Path, *arguments: str) -> str | None:
    result = subprocess.run(
        ["git", *arguments], cwd=repo, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def build_bundle(repo: Path, output: Path, max_bytes: int) -> dict:
    files = [repo / relative for relative in REQUIRED_FILES]
    missing = [str(path.relative_to(repo)) for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Required experiment artifacts are missing: {missing}")
    audit = json.loads((repo / "artifacts/audit/aggregation_asv_test_audit.json").read_text())
    if audit.get("ok") is not True:
        raise RuntimeError("Refusing to package an experiment whose audit did not pass")

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_value(repo, "rev-parse", "HEAD"),
        "git_branch": git_value(repo, "branch", "--show-current"),
        "scope": "Experiment results only; excludes VCTK, pretrained encoders and Python environments.",
        "restore": "Extract at the CloneBlock_RT repository root and verify every SHA-256 below.",
        "files": [
            {
                "path": str(path.relative_to(repo)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
    }
    recovery_manifest = repo / "artifacts/recovery/aggregation_advantage_files.json"
    recovery_manifest.parent.mkdir(parents=True, exist_ok=True)
    recovery_manifest.write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    files.append(recovery_manifest)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, mode="w:gz", compresslevel=9) as archive:
        for path in files:
            archive.add(path, arcname=str(path.relative_to(repo)).replace("\\", "/"))
    size = output.stat().st_size
    if size >= max_bytes:
        raise RuntimeError(
            f"Compressed result bundle is {size / 1024**2:.1f} MiB, above the configured "
            f"GitHub-safe limit of {max_bytes / 1024**2:.1f} MiB"
        )
    bundle_hash = sha256(output)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{bundle_hash}  {output.name}\n", encoding="ascii"
    )
    return {
        "ok": True,
        "bundle": str(output),
        "bytes": size,
        "sha256": bundle_hash,
        "files": len(files),
        "recovery_manifest": str(recovery_manifest),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/bundles/aggregation_advantage_results.tar.gz"),
    )
    parser.add_argument("--max_mib", type=float, default=95.0)
    args = parser.parse_args()
    repo = args.repo.resolve()
    output = args.output if args.output.is_absolute() else repo / args.output
    report = build_bundle(repo, output, int(args.max_mib * 1024**2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
