#!/usr/bin/env python3
"""Verify and optionally restore an aggregation experiment result bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


MANIFEST_PATH = PurePosixPath("artifacts/recovery/aggregation_advantage_files.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_members(archive: tarfile.TarFile) -> dict[PurePosixPath, tarfile.TarInfo]:
    members: dict[PurePosixPath, tarfile.TarInfo] = {}
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError(f"Unsafe archive path: {member.name}")
        if not member.isfile():
            raise ValueError(f"Only regular files are permitted: {member.name}")
        if path in members:
            raise ValueError(f"Duplicate archive path: {member.name}")
        members[path] = member
    if MANIFEST_PATH not in members:
        raise ValueError(f"Bundle lacks {MANIFEST_PATH}")
    return members


def verify_bundle(bundle: Path, restore_to: Path | None, overwrite: bool) -> dict:
    checksum_file = bundle.with_suffix(bundle.suffix + ".sha256")
    bundle_hash = sha256(bundle)
    if checksum_file.is_file():
        expected = checksum_file.read_text(encoding="ascii").split()[0]
        if expected != bundle_hash:
            raise ValueError("Bundle SHA-256 does not match its sidecar")

    with tempfile.TemporaryDirectory(prefix="cloneblock-results-") as directory:
        temporary = Path(directory)
        with tarfile.open(bundle, mode="r:gz") as archive:
            members = safe_members(archive)
            for path, member in members.items():
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError(f"Cannot read archive member: {path}")
                destination = temporary.joinpath(*path.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("wb") as stream:
                    shutil.copyfileobj(source, stream)

        manifest = json.loads(temporary.joinpath(*MANIFEST_PATH.parts).read_text(encoding="utf-8"))
        expected_paths = {PurePosixPath(item["path"]): item for item in manifest.get("files", [])}
        actual_payload = set(members) - {MANIFEST_PATH}
        if set(expected_paths) != actual_payload:
            missing = sorted(str(path) for path in set(expected_paths) - actual_payload)
            extra = sorted(str(path) for path in actual_payload - set(expected_paths))
            raise ValueError(f"Bundle contents disagree with manifest; missing={missing}, extra={extra}")

        verified = []
        for path, record in expected_paths.items():
            extracted = temporary.joinpath(*path.parts)
            if extracted.stat().st_size != int(record["bytes"]):
                raise ValueError(f"Size mismatch: {path}")
            digest = sha256(extracted)
            if digest != record["sha256"]:
                raise ValueError(f"SHA-256 mismatch: {path}")
            verified.append(str(path))

        restored = []
        if restore_to is not None:
            restore_to = restore_to.resolve()
            for path in [*expected_paths, MANIFEST_PATH]:
                source = temporary.joinpath(*path.parts)
                destination = restore_to.joinpath(*path.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    if destination.is_file() and sha256(destination) == sha256(source):
                        continue
                    if not overwrite:
                        raise FileExistsError(
                            f"Refusing to replace different existing result: {destination}"
                        )
                shutil.copy2(source, destination)
                restored.append(str(path))

    return {
        "ok": True,
        "bundle": str(bundle),
        "bundle_sha256": bundle_hash,
        "verified_files": len(verified),
        "restored_files": len(restored),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--restore_to", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.overwrite and args.restore_to is None:
        parser.error("--overwrite is meaningful only with --restore_to")
    print(
        json.dumps(
            verify_bundle(args.bundle.resolve(), args.restore_to, args.overwrite), indent=2
        )
    )


if __name__ == "__main__":
    main()
