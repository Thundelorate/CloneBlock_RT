#!/usr/bin/env python3
"""Verify official corpus archives before extracting or using them."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile


CORPORA = {
    "vctk": {
        "archive": "VCTK-Corpus-0.92.zip",
        "size": 11747302977,
        "md5": "8a6ba2946b36fcbef0212cad601f4bfa",
        "expected_sha256": "f96258be9fdc2cbff6559541aae7ea4f59df3fcaf5cf963aae5ca647357e359c",
        "directory": "VCTK-Corpus-0.92",
        "source": "https://datashare.ed.ac.uk/server/api/core/bitstreams/535f4286-e54c-4038-838c-a02285e32cb2/content",
    },
    "librispeech": {
        "archive": "dev-clean.tar.gz",
        "size": 337926286,
        "md5": "42e2234ba48799c1f50f24a7926300a1",
        "directory": "LibriSpeech",
        "source": "https://www.openslr.org/resources/12/dev-clean.tar.gz",
    },
}


def checked_path(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Unsafe archive member: {name}")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=CORPORA, required=True)
    parser.add_argument("--raw_dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--report_dir", type=Path, default=Path("artifacts/audit"))
    args = parser.parse_args()
    spec = CORPORA[args.dataset]
    archive = args.raw_dir / spec["archive"]
    candidate = archive if archive.exists() else archive.with_name(archive.name + ".part")
    if candidate.stat().st_size != spec["size"]:
        raise ValueError(f"Incomplete archive: {candidate}")
    md5, sha256 = hashlib.md5(), hashlib.sha256()
    with candidate.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            md5.update(block)
            sha256.update(block)
    if md5.hexdigest() != spec["md5"]:
        raise ValueError(f"Official MD5 mismatch: {candidate}")
    if spec.get("expected_sha256") and sha256.hexdigest() != spec["expected_sha256"]:
        raise ValueError(f"Published SHA-256 mismatch: {candidate}")
    if candidate != archive:
        candidate.rename(archive)
    report = {**spec, "sha256": sha256.hexdigest(), "verified": True}
    args.report_dir.mkdir(parents=True, exist_ok=True)
    (args.report_dir / f"{args.dataset}_archive.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[archive] verified {archive}, sha256={sha256.hexdigest()}", flush=True)

    destination = args.raw_dir / spec["directory"]
    marker = destination / ".cloneblock_verified_archive.json"
    if destination.exists():
        if marker.is_file() and json.loads(marker.read_text())["sha256"] == sha256.hexdigest():
            print(f"[archive] already extracted: {destination}", flush=True)
            return
        raise FileExistsError(f"Refusing to overwrite unverified extraction: {destination}")
    staging = args.raw_dir / (".extract-" + args.dataset)
    staging.mkdir(parents=True, exist_ok=True)
    if args.dataset == "vctk":
        with zipfile.ZipFile(archive) as handle:
            for member in handle.infolist():
                checked_path(staging, member.filename)
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Archive symlinks are not supported")
            handle.extractall(staging)
        staging.rename(destination)
    else:
        with tarfile.open(archive, "r:gz") as handle:
            for member in handle.getmembers():
                checked_path(staging, member.name)
                if not (member.isfile() or member.isdir()):
                    raise ValueError(f"Unsupported archive member: {member.name}")
            handle.extractall(staging)
        (staging / "LibriSpeech").rename(destination)
        staging.rmdir()
    marker.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"[archive] extracted {destination}", flush=True)


if __name__ == "__main__":
    main()
