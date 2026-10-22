#!/usr/bin/env python3
"""Run independent-enrollment ASV evaluation for multi-fragment attacks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import torch
import torchaudio.functional as audio_functional
import yaml
from speechbrain.inference.speaker import EncoderClassifier

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.metrics.aggregation_protocol import (
    aggregate_embeddings,
    contiguous_self_consistency_indices,
    enrollment_centroid,
    greedy_non_overlapping_indices,
    l2_normalize,
    random_k_indices,
    score_against_enrollments,
    self_consistency_indices,
    stable_seed,
    threshold_at_far,
)
from src.models.defense_stftmask import STFTMaskDefense
from src.transforms.telephony import TelephonyTransform


@dataclass(frozen=True)
class Window:
    speaker: str
    session: str
    path: Path
    start: float
    end: float
    row_index: int


@dataclass
class Session:
    speaker: str
    session: str
    windows: list[Window]
    waveforms: np.ndarray

    @property
    def starts(self) -> np.ndarray:
        return np.asarray([window.start for window in self.windows], dtype=np.float64)

    @property
    def ends(self) -> np.ndarray:
        return np.asarray([window.end for window in self.windows], dtype=np.float64)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def directory_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        raise FileNotFoundError(f"No model files found under {path}")
    for item in files:
        digest.update(str(item.relative_to(path)).replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        with item.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def first_present(fieldnames: list[str], aliases: tuple[str, ...], label: str) -> str:
    for name in aliases:
        if name in fieldnames:
            return name
    raise ValueError(f"Session pool lacks a {label} column; tried {aliases}")


def load_window_rows(path: Path, window_sec: float) -> list[Window]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or ())
        speaker_column = first_present(
            fields, ("speaker", "speaker_id", "spk", "spk_id"), "speaker"
        )
        session_column = first_present(
            fields, ("session", "session_id", "session_idx", "session_index"), "session"
        )
        path_column = first_present(
            fields,
            ("path", "wav_path", "audio_path", "session_path", "source_path", "file", "wav"),
            "audio path",
        )
        start_column = first_present(
            fields,
            ("start_sec", "window_start_sec", "window_start", "segment_start_sec", "start", "offset_sec"),
            "window start",
        )
        end_column = next(
            (
                name
                for name in ("end_sec", "window_end_sec", "window_end", "segment_end_sec", "end")
                if name in fields
            ),
            None,
        )
        rows = []
        for row_index, row in enumerate(reader):
            audio_path = Path(row[path_column])
            if not audio_path.is_absolute():
                audio_path = REPO / audio_path
            start = float(row[start_column])
            end = float(row[end_column]) if end_column and row[end_column] else start + window_sec
            rows.append(
                Window(
                    speaker=row[speaker_column],
                    session=row[session_column],
                    path=audio_path,
                    start=start,
                    end=end,
                    row_index=row_index,
                )
            )
    if not rows:
        raise ValueError(f"Session pool is empty: {path}")
    return rows


def read_window(
    window: Window,
    sample_rate: int,
    samples: int,
    audio_cache: dict[Path, tuple[np.ndarray, int]] | None = None,
) -> np.ndarray:
    cached = audio_cache.get(window.path) if audio_cache is not None else None
    if cached is None:
        waveform, source_rate = sf.read(window.path, dtype="float32", always_2d=True)
        waveform = waveform.mean(axis=1)
        if audio_cache is not None:
            audio_cache[window.path] = (waveform, source_rate)
    else:
        waveform, source_rate = cached
    source_duration = len(waveform) / source_rate
    requested_duration = window.end - window.start
    if window.end <= source_duration + 1e-4:
        begin = max(0, int(round(window.start * source_rate)))
        finish = min(len(waveform), int(round(window.end * source_rate)))
        waveform = waveform[begin:finish]
    elif abs(source_duration - requested_duration) > 0.1:
        raise ValueError(
            f"Window {window.path} cannot satisfy [{window.start}, {window.end}] "
            f"from {source_duration:.3f}s audio"
        )
    if source_rate != sample_rate:
        tensor = torch.from_numpy(waveform)
        waveform = audio_functional.resample(tensor, source_rate, sample_rate).numpy()
    if len(waveform) < samples:
        waveform = np.pad(waveform, (0, samples - len(waveform)))
    elif len(waveform) > samples:
        waveform = waveform[:samples]
    if not np.all(np.isfinite(waveform)):
        raise ValueError(f"Nonfinite samples in {window.path}")
    return waveform.astype(np.float32, copy=False)


def load_sessions(
    pool: Path, sample_rate: int, window_sec: float, min_windows: int
) -> dict[tuple[str, str], Session]:
    grouped: dict[tuple[str, str], list[Window]] = {}
    for window in load_window_rows(pool, window_sec):
        grouped.setdefault((window.speaker, window.session), []).append(window)
    sessions: dict[tuple[str, str], Session] = {}
    samples = int(round(sample_rate * window_sec))
    for key in sorted(grouped):
        windows = grouped[key]
        selected = greedy_non_overlapping_indices(
            [window.start for window in windows], [window.end for window in windows]
        )
        retained = [windows[int(index)] for index in selected]
        retained.sort(key=lambda window: (window.start, window.end, window.row_index))
        if len(retained) < min_windows:
            raise ValueError(f"Session {key} has only {len(retained)} non-overlapping windows")
        audio_cache: dict[Path, tuple[np.ndarray, int]] = {}
        waveforms = np.stack(
            [read_window(window, sample_rate, samples, audio_cache) for window in retained]
        )
        sessions[key] = Session(key[0], key[1], retained, waveforms)
    per_speaker: dict[str, int] = {}
    for speaker, _ in sessions:
        per_speaker[speaker] = per_speaker.get(speaker, 0) + 1
    incomplete = {speaker: count for speaker, count in per_speaker.items() if count < 3}
    if incomplete:
        raise ValueError(f"Every speaker needs three sessions; incomplete={incomplete}")
    return sessions


def checkpoint_state(payload: Any) -> dict[str, torch.Tensor]:
    if isinstance(payload, dict):
        if payload and all(torch.is_tensor(value) for value in payload.values()):
            return payload
        for key in ("model_state_dict", "state_dict", "model", "defense", "defense_state_dict"):
            if key in payload:
                try:
                    return checkpoint_state(payload[key])
                except ValueError:
                    pass
    raise ValueError("Checkpoint does not contain a recognizable defense state dict")


def load_defense(path: Path | None, device: torch.device) -> STFTMaskDefense | None:
    if path is None:
        return None
    payload = torch.load(path, map_location="cpu")
    state = checkpoint_state(payload)
    model = STFTMaskDefense().to(device)
    candidates = [state]
    for prefix in ("module.", "model.", "defense."):
        if state and all(key.startswith(prefix) for key in state):
            candidates.append({key[len(prefix) :]: value for key, value in state.items()})
    failures = []
    for candidate in candidates:
        try:
            model.load_state_dict(candidate, strict=True)
            break
        except RuntimeError as exc:
            failures.append(str(exc))
    else:
        raise RuntimeError(
            f"Checkpoint {path} does not strictly match STFTMaskDefense under known prefixes: "
            + " | ".join(failures)
        )
    model.eval()
    return model


def load_encoder(source: str, savedir: Path, device: torch.device) -> EncoderClassifier:
    return EncoderClassifier.from_hparams(
        source=source,
        savedir=str(savedir),
        run_opts={"device": str(device)},
    )


def encode(encoder: EncoderClassifier, waveforms: np.ndarray, device: torch.device) -> np.ndarray:
    tensor = torch.from_numpy(waveforms).to(device)
    with torch.inference_mode():
        embeddings = encoder.encode_batch(tensor).detach().cpu().numpy()
    return embeddings.reshape(len(waveforms), -1).astype(np.float64)


def transform_queries(
    waveforms: np.ndarray,
    defense: STFTMaskDefense | None,
    telephony: TelephonyTransform,
    sample_rate: int,
    device: torch.device,
    telephony_params: list[dict[str, Any]] | None = None,
) -> np.ndarray:
    if telephony_params is not None and len(telephony_params) != len(waveforms):
        raise ValueError("telephony_params must align one-to-one with waveforms")
    if defense is None:
        defended = waveforms
    else:
        tensor = torch.from_numpy(waveforms).to(device)
        with torch.inference_mode():
            defended = defense(tensor).detach().cpu().numpy()
    transformed = []
    for index, signal in enumerate(defended):
        signal = signal.astype(np.float32)
        if telephony_params is None:
            transformed_signal = telephony(signal, sample_rate=sample_rate)
        else:
            transformed_signal = telephony.apply_with_params(
                signal, sample_rate=sample_rate, params=telephony_params[index]
            )
        transformed.append(np.asarray(transformed_signal, dtype=np.float32))
    output = np.stack(transformed)
    if output.shape != waveforms.shape or not np.all(np.isfinite(output)):
        raise ValueError("Telephony transform returned invalid query waveforms")
    return output


def concatenate_selected_windows(waveforms: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Return one chronological waveform for the equal-duration contiguous control."""
    selected = np.asarray(indices, dtype=np.int64)
    if waveforms.ndim != 2 or selected.ndim != 1 or not len(selected):
        raise ValueError("A 2D waveform matrix and nonempty indices are required")
    if np.any(selected < 0) or np.any(selected >= len(waveforms)):
        raise IndexError("Contiguous-control index outside the waveform matrix")
    if np.any(np.diff(selected) != 1):
        raise ValueError("Contiguous-control indices must be consecutive")
    return np.concatenate(waveforms[selected], axis=0)[None, :]


def selection_identifier(*parts: object) -> str:
    encoded = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def load_embedding_cache(path: Path, fingerprint: str, expected_rows: int) -> np.ndarray | None:
    if not path.is_file():
        return None
    try:
        with np.load(path, allow_pickle=False) as payload:
            cached_fingerprint = str(payload["fingerprint"].item())
            embeddings = np.asarray(payload["embeddings"], dtype=np.float64)
    except (OSError, KeyError, ValueError):
        return None
    if cached_fingerprint != fingerprint or embeddings.ndim != 2 or len(embeddings) != expected_rows:
        return None
    if not np.all(np.isfinite(embeddings)):
        return None
    return embeddings


def save_embedding_cache(path: Path, fingerprint: str, embeddings: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, fingerprint=np.asarray(fingerprint), embeddings=embeddings)
    temporary.replace(path)


def git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def parse_checkpoints(values: list[str]) -> dict[str, Path | None]:
    methods: dict[str, Path | None] = {"none": None}
    for value in values:
        if "=" not in value:
            raise ValueError("--checkpoint must be NAME=PATH")
        name, raw_path = value.split("=", 1)
        if name in methods or not name:
            raise ValueError(f"Duplicate or empty method name: {name}")
        path = Path(raw_path)
        if not path.is_absolute():
            path = REPO / path
        if not path.is_file():
            raise FileNotFoundError(path)
        methods[name] = path
    required = {"none", "reference", "realistic"}
    if set(methods) != required:
        raise ValueError(f"Methods must be exactly {sorted(required)}, found {sorted(methods)}")
    return methods


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session_pool", type=Path, required=True)
    parser.add_argument("--split", choices=("validation", "test"), required=True)
    parser.add_argument("--checkpoint", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--telephony_config", type=Path, default=REPO / "configs/telephony.yaml")
    parser.add_argument("--ecapa_source", default="speechbrain/spkrec-ecapa-voxceleb")
    parser.add_argument("--xvector_source", default="speechbrain/spkrec-xvect-voxceleb")
    parser.add_argument("--ecapa_savedir", type=Path, default=REPO / "models/spkrec-ecapa-voxceleb")
    parser.add_argument("--xvector_savedir", type=Path, default=REPO / "models/spkrec-xvect-voxceleb")
    parser.add_argument("--thresholds", type=Path)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--sample_rate", type=int, default=16000)
    parser.add_argument("--window_sec", type=float, default=1.0)
    parser.add_argument("--ks", type=int, nargs="+", default=[1, 2, 4, 8, 16])
    parser.add_argument("--random_repeats", type=int, default=100)
    parser.add_argument("--target_far", type=float, default=0.01)
    parser.add_argument("--bootstrap_draws", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    if args.split == "test" and not args.thresholds:
        parser.error("--thresholds from validation is required for test")
    if args.split == "validation" and args.thresholds:
        parser.error("validation computes thresholds; do not pass --thresholds")
    methods = parse_checkpoints(args.checkpoint)
    if not torch.cuda.is_available() and args.device.startswith("cuda"):
        raise RuntimeError("CUDA requested but unavailable")
    device = torch.device(args.device)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    session_pool = args.session_pool if args.session_pool.is_absolute() else REPO / args.session_pool
    session_pool_hash = file_sha256(session_pool)
    session_pool_manifest = session_pool.parent / "aggregation_session_pool_manifest.json"
    if not session_pool_manifest.is_file():
        raise FileNotFoundError(
            f"Missing aggregation session-pool provenance manifest: {session_pool_manifest}"
        )
    session_pool_provenance = json.loads(
        session_pool_manifest.read_text(encoding="utf-8")
    )
    split_provenance = next(
        (
            item
            for item in session_pool_provenance.get("splits", [])
            if item.get("split") == args.split
        ),
        None,
    )
    if split_provenance is None:
        raise ValueError(f"Session-pool manifest lacks split {args.split}")
    if split_provenance.get("pool_sha256") != session_pool_hash:
        raise ValueError("Session pool does not match its provenance manifest")
    telephony_config_path = (
        args.telephony_config
        if args.telephony_config.is_absolute()
        else REPO / args.telephony_config
    )
    telephony_config_hash = file_sha256(telephony_config_path)
    minimum_windows = max(args.ks)
    sessions = load_sessions(session_pool, args.sample_rate, args.window_sec, minimum_windows)
    speakers = sorted({speaker for speaker, _ in sessions})
    enrollment_keys: dict[str, tuple[str, str]] = {}
    attack_keys: list[tuple[str, str]] = []
    for speaker in speakers:
        keys = sorted(key for key in sessions if key[0] == speaker)
        enrollment_keys[speaker] = keys[0]
        attack_keys.extend(keys[1:])

    encoders = {
        "ecapa": load_encoder(args.ecapa_source, args.ecapa_savedir, device),
        "xvector": load_encoder(args.xvector_source, args.xvector_savedir, device),
    }
    encoder_model_hashes = {
        "ecapa": directory_sha256(args.ecapa_savedir),
        "xvector": directory_sha256(args.xvector_savedir),
    }
    enrollments: dict[str, dict[str, np.ndarray]] = {name: {} for name in encoders}
    for encoder_name, encoder in encoders.items():
        for speaker in speakers:
            session = sessions[enrollment_keys[speaker]]
            enrollments[encoder_name][speaker] = enrollment_centroid(
                encode(encoder, session.waveforms, device)
            )

    telephony_payload = yaml.safe_load(telephony_config_path.read_text(encoding="utf-8")) or {}
    telephony_config = telephony_payload.get("telephony", telephony_payload)
    aggregate_rows: list[dict[str, Any]] = []
    trial_rows: list[dict[str, Any]] = []
    started = time.monotonic()
    total_units = len(methods) * len(attack_keys)
    completed_units = 0
    cache_hits = 0

    for method, checkpoint in methods.items():
        random.seed(args.seed)
        np.random.seed(args.seed)
        torch.manual_seed(args.seed)
        defense = load_defense(checkpoint, device)
        for key in attack_keys:
            session = sessions[key]
            session_token = selection_identifier(session.speaker, session.session)
            checkpoint_hash = file_sha256(checkpoint) if checkpoint is not None else "none"
            source_by_encoder = {
                "ecapa": args.ecapa_source,
                "xvector": args.xvector_source,
            }
            channel_seed = stable_seed(
                args.seed, "telephony", session.speaker, session.session
            ) % (2**31)
            random.seed(channel_seed)
            np.random.seed(channel_seed)
            torch.manual_seed(channel_seed)
            telephony = TelephonyTransform(telephony_config, seed=channel_seed)
            window_telephony_params = [
                telephony.sample_params() for _ in range(len(session.waveforms))
            ]
            query_waveforms = transform_queries(
                session.waveforms,
                defense,
                telephony,
                args.sample_rate,
                device,
                telephony_params=window_telephony_params,
            )

            embeddings_by_encoder: dict[str, np.ndarray] = {}
            cache_records: dict[str, tuple[Path, str]] = {}
            for encoder_name in encoders:
                fingerprint = selection_identifier(
                    "aggregation-embedding-cache-v1",
                    args.split,
                    session_pool_hash,
                    telephony_config_hash,
                    method,
                    checkpoint_hash,
                    encoder_name,
                    source_by_encoder[encoder_name],
                    encoder_model_hashes[encoder_name],
                    args.sample_rate,
                    args.window_sec,
                    session.speaker,
                    session.session,
                )
                cache_path = (
                    args.output_dir
                    / "cache"
                    / f"{args.split}_{method}_{encoder_name}_{session_token}.npz"
                )
                cache_records[encoder_name] = (cache_path, fingerprint)
                cached = load_embedding_cache(cache_path, fingerprint, len(session.waveforms))
                if cached is not None:
                    embeddings_by_encoder[encoder_name] = cached
                    cache_hits += 1

            if len(embeddings_by_encoder) != len(encoders):
                for encoder_name, encoder in encoders.items():
                    if encoder_name in embeddings_by_encoder:
                        continue
                    embeddings = encode(encoder, query_waveforms, device)
                    embeddings_by_encoder[encoder_name] = embeddings
                    cache_path, fingerprint = cache_records[encoder_name]
                    save_embedding_cache(cache_path, fingerprint, embeddings)

            for encoder_name, encoder in encoders.items():
                embeddings = embeddings_by_encoder[encoder_name]
                for k in args.ks:
                    selections: list[tuple[str, int, np.ndarray]] = []
                    random_draws = random_k_indices(
                        range(len(embeddings)),
                        k,
                        args.random_repeats,
                        args.seed,
                        session.speaker,
                        session.session,
                    )
                    selections.extend(("random_K", repeat, indices) for repeat, indices in enumerate(random_draws))
                    self_consistency = self_consistency_indices(embeddings, k)
                    contiguous = contiguous_self_consistency_indices(
                        embeddings, session.starts, session.ends, k
                    )
                    if k == 1 and not np.array_equal(self_consistency, contiguous):
                        raise AssertionError("K=1 controls must select the same window")
                    selections.append(("self_consistency_K", 0, self_consistency))
                    selections.append(
                        ("contiguous_K", 0, contiguous)
                    )
                    paired_k1_embedding: np.ndarray | None = None
                    for strategy, repeat, indices in selections:
                        if k == 1 and strategy in {
                            "self_consistency_K", "contiguous_K"
                        }:
                            if paired_k1_embedding is None:
                                paired_k1_embedding = encode(
                                    encoder, query_waveforms[indices], device
                                )[0]
                            attack_embedding = paired_k1_embedding.copy()
                            representation = (
                                "single_contiguous_waveform"
                                if strategy == "contiguous_K"
                                else "fragment_embedding_mean"
                            )
                        elif strategy == "contiguous_K":
                            contiguous_query = concatenate_selected_windows(
                                query_waveforms, indices
                            )
                            attack_embedding = encode(
                                encoder, contiguous_query, device
                            )[0]
                            representation = "single_contiguous_waveform"
                        else:
                            attack_embedding = aggregate_embeddings(embeddings, indices)
                            representation = "fragment_embedding_mean"
                        attack_embedding = l2_normalize(attack_embedding)
                        scores = score_against_enrollments(
                            attack_embedding, session.speaker, enrollments[encoder_name]
                        )
                        selected_starts = session.starts[indices]
                        selected_ends = session.ends[indices]
                        selection_id = selection_identifier(
                            encoder_name if strategy != "random_K" else "paired",
                            method if strategy != "random_K" else "paired",
                            session.speaker,
                            session.session,
                            strategy,
                            k,
                            repeat,
                            ",".join(map(str, indices.tolist())),
                        )
                        aggregate_rows.append(
                            {
                                "split": args.split,
                                "method": method,
                                "encoder": encoder_name,
                                "speaker": session.speaker,
                                "enrollment_session": enrollment_keys[session.speaker][1],
                                "attack_session": session.session,
                                "strategy": strategy,
                                "representation": representation,
                                "k": k,
                                "repeat": repeat,
                                "selection_id": selection_id,
                                "selected_indices": json.dumps(indices.tolist(), separators=(",", ":")),
                                "selected_intervals": json.dumps(
                                    [
                                        [float(start), float(end)]
                                        for start, end in zip(selected_starts, selected_ends)
                                    ],
                                    separators=(",", ":"),
                                ),
                                "selected_duration_sec": float(
                                    np.sum(selected_ends - selected_starts)
                                ),
                                "selection_span_sec": float(
                                    selected_ends.max() - selected_starts.min()
                                ),
                                "target_score": scores["target_score"],
                                "max_impostor_score": scores["max_impostor_score"],
                                "margin": scores["margin"],
                                "threshold": "",
                            }
                        )
                        for enrollment_speaker, enrollment in enrollments[encoder_name].items():
                            trial_rows.append(
                                {
                                    "split": args.split,
                                    "method": method,
                                    "encoder": encoder_name,
                                    "speaker": session.speaker,
                                    "enrollment_speaker": enrollment_speaker,
                                    "enrollment_session": enrollment_keys[enrollment_speaker][1],
                                    "attack_session": session.session,
                                    "strategy": strategy,
                                    "representation": representation,
                                    "k": k,
                                    "repeat": repeat,
                                    "selection_id": selection_id,
                                    "label": "target" if enrollment_speaker == session.speaker else "impostor",
                                    "score": float(attack_embedding @ enrollment),
                                }
                            )

            completed_units += 1
            elapsed = time.monotonic() - started
            rate = completed_units / elapsed if elapsed > 0 else 0.0
            eta = (total_units - completed_units) / rate if rate > 0 else float("nan")
            print(
                f"[aggregation-asv] {completed_units}/{total_units} "
                f"({100 * completed_units / total_units:.1f}%) method={method} "
                f"speaker={session.speaker} session={session.session} "
                f"cache_hits={cache_hits} elapsed_min={elapsed / 60:.1f} "
                f"eta_min={eta / 60:.1f}",
                flush=True,
            )

    if args.split == "validation":
        thresholds = {}
        for encoder_name in encoders:
            scores = [
                float(row["score"])
                for row in trial_rows
                if row["encoder"] == encoder_name
                and row["method"] == "none"
                and row["strategy"] == "random_K"
                and int(row["k"]) == 1
                and row["label"] == "impostor"
            ]
            thresholds[encoder_name] = threshold_at_far(scores, args.target_far)
        threshold_source_sha256 = None
    else:
        threshold_payload = json.loads(args.thresholds.read_text(encoding="utf-8"))
        thresholds = {name: float(value) for name, value in threshold_payload["thresholds"].items()}
        threshold_source_sha256 = file_sha256(args.thresholds)
    for row in aggregate_rows:
        row["threshold"] = thresholds[row["encoder"]]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    aggregates_path = args.output_dir / f"aggregation_asv_{args.split}_aggregates.csv"
    trials_path = args.output_dir / f"aggregation_asv_{args.split}_trials.csv"
    thresholds_path = args.output_dir / f"aggregation_asv_{args.split}_thresholds.json"
    manifest_path = args.output_dir / f"aggregation_asv_{args.split}_manifest.json"
    write_csv(aggregates_path, aggregate_rows)
    write_csv(trials_path, trial_rows)
    thresholds_payload = {
        "split": args.split,
        "target_far": args.target_far,
        "thresholds": thresholds,
        "calibration_condition": "none/random_K/K1 validation impostors",
    }
    thresholds_path.write_text(json.dumps(thresholds_payload, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "git_commit": git_commit(),
        "source_file_sha256": {
            "scripts/run_aggregation_advantage_asv.py": file_sha256(Path(__file__)),
            "src/metrics/aggregation_protocol.py": file_sha256(
                REPO / "src/metrics/aggregation_protocol.py"
            ),
            "src/models/defense_stftmask.py": file_sha256(
                REPO / "src/models/defense_stftmask.py"
            ),
            "src/transforms/telephony.py": file_sha256(
                REPO / "src/transforms/telephony.py"
            ),
        },
        "split": args.split,
        "protocol": {
            "dataset": "VCTK-0.92-mic2",
            "dataset_archive_md5": "8a6ba2946b36fcbef0212cad601f4bfa",
            "dataset_archive_md5_verified": (
                session_pool_provenance.get("source_kind") == "official_archive"
                and session_pool_provenance.get("source_archive_md5")
                == "8a6ba2946b36fcbef0212cad601f4bfa"
            ),
            "seed": args.seed,
            "k_values": args.ks,
            "random_repeats": args.random_repeats,
            "bootstrap_draws": args.bootstrap_draws,
            "target_far": args.target_far,
            "independent_enrollment": True,
            "non_overlapping_attack_windows": True,
            "same_total_duration_control": True,
            "same_total_duration_control_representation": (
                "single encoder pass over the exact concatenation of the same "
                "telephony-transformed selected windows"
            ),
            "telephony_pairing": (
                "deterministic per-session/per-window parameters shared across systems; "
                "fragmented and contiguous representations reuse identical transformed samples"
            ),
            "validation_threshold_frozen_before_test": args.split == "test",
            "enrollment_rule": "first deterministically sorted session",
            "attack_rule": "remaining sessions",
        },
        "methods": list(methods),
        "encoders": list(encoders),
        "encoder_model_sha256": encoder_model_hashes,
        "strategies": ["random_K", "self_consistency_K", "contiguous_K"],
        "speakers": speakers,
        "session_pool": str(session_pool.relative_to(REPO)),
        "session_pool_sha256": session_pool_hash,
        "session_pool_manifest_sha256": file_sha256(session_pool_manifest),
        "session_pool_source_kind": session_pool_provenance.get("source_kind"),
        "session_pool_source_commit": session_pool_provenance.get("source_commit"),
        "session_pool_source_archive_md5": session_pool_provenance.get(
            "source_archive_md5"
        ),
        "session_pool_source_audit_sha256": session_pool_provenance.get(
            "source_audit_sha256"
        ),
        "telephony_config_sha256": telephony_config_hash,
        "checkpoint_sha256": {
            name: file_sha256(path) for name, path in methods.items() if path is not None
        },
        "thresholds": thresholds,
        "threshold_source_sha256": threshold_source_sha256,
        "outputs": {
            "aggregates": str(aggregates_path),
            "aggregates_sha256": file_sha256(aggregates_path),
            "trials": str(trials_path),
            "trials_sha256": file_sha256(trials_path),
        },
        "versions": {
            package: importlib.metadata.version(package)
            for package in ("numpy", "soundfile", "torch", "torchaudio", "speechbrain")
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "manifest": str(manifest_path), "rows": len(aggregate_rows),
                      "trials": len(trial_rows), "thresholds": thresholds}, indent=2))


if __name__ == "__main__":
    main()
