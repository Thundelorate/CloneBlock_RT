"""Deterministic selection and scoring helpers for aggregation attacks."""

from __future__ import annotations

import hashlib
from typing import Iterable, Sequence

import numpy as np


def stable_seed(seed: int, *parts: object) -> int:
    """Derive a process-independent NumPy seed from experiment identifiers."""
    payload = "\x1f".join([str(seed), *(str(part) for part in parts)]).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little", signed=False)


def l2_normalize(values: np.ndarray, axis: int = -1) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    norm = np.linalg.norm(array, axis=axis, keepdims=True)
    if np.any(norm <= 0) or not np.all(np.isfinite(norm)):
        raise ValueError("Embeddings must have finite, nonzero L2 norms")
    return array / norm


def greedy_non_overlapping_indices(
    starts: Sequence[float], ends: Sequence[float], tolerance: float = 1e-8
) -> np.ndarray:
    """Keep a deterministic maximum chronological set under interval overlap."""
    starts_array = np.asarray(starts, dtype=np.float64)
    ends_array = np.asarray(ends, dtype=np.float64)
    if starts_array.shape != ends_array.shape or starts_array.ndim != 1:
        raise ValueError("starts and ends must be one-dimensional arrays of equal length")
    if np.any(~np.isfinite(starts_array)) or np.any(~np.isfinite(ends_array)):
        raise ValueError("Window boundaries must be finite")
    if np.any(ends_array <= starts_array):
        raise ValueError("Every window must have positive duration")

    order = np.lexsort((np.arange(len(starts_array)), starts_array, ends_array))
    selected: list[int] = []
    last_end = -np.inf
    for index in order:
        if starts_array[index] + tolerance >= last_end:
            selected.append(int(index))
            last_end = float(ends_array[index])
    return np.asarray(selected, dtype=np.int64)


def random_k_indices(
    candidate_indices: Sequence[int],
    k: int,
    repeats: int,
    seed: int,
    *seed_parts: object,
) -> list[np.ndarray]:
    """Produce paired random selections reusable across defense systems."""
    candidates = np.asarray(candidate_indices, dtype=np.int64)
    if candidates.ndim != 1 or len(np.unique(candidates)) != len(candidates):
        raise ValueError("candidate_indices must be a one-dimensional set")
    if not 1 <= k <= len(candidates):
        raise ValueError("k must be between one and the number of candidates")
    if repeats < 1:
        raise ValueError("repeats must be positive")
    rng = np.random.default_rng(stable_seed(seed, *seed_parts, k))
    return [np.sort(rng.choice(candidates, size=k, replace=False)) for _ in range(repeats)]


def aggregate_embeddings(embeddings: np.ndarray, indices: Sequence[int]) -> np.ndarray:
    matrix = l2_normalize(np.asarray(embeddings, dtype=np.float64), axis=1)
    chosen = np.asarray(indices, dtype=np.int64)
    if chosen.ndim != 1 or len(chosen) == 0:
        raise ValueError("At least one embedding index is required")
    if np.any(chosen < 0) or np.any(chosen >= len(matrix)):
        raise IndexError("Embedding index outside the candidate matrix")
    return l2_normalize(matrix[chosen].mean(axis=0))


def self_consistency_indices(embeddings: np.ndarray, k: int) -> np.ndarray:
    """Select windows closest to the attacker-visible full-session centroid."""
    matrix = l2_normalize(np.asarray(embeddings, dtype=np.float64), axis=1)
    if not 1 <= k <= len(matrix):
        raise ValueError("k must be between one and the number of embeddings")
    centroid = l2_normalize(matrix.mean(axis=0))
    scores = matrix @ centroid
    order = np.lexsort((np.arange(len(matrix)), -scores))
    return np.sort(order[:k]).astype(np.int64)


def contiguous_self_consistency_indices(
    embeddings: np.ndarray,
    starts: Sequence[float],
    ends: Sequence[float],
    k: int,
    gap_tolerance: float = 0.02,
) -> np.ndarray:
    """Choose a K-second chronological block with the same aggregation rule."""
    matrix = l2_normalize(np.asarray(embeddings, dtype=np.float64), axis=1)
    starts_array = np.asarray(starts, dtype=np.float64)
    ends_array = np.asarray(ends, dtype=np.float64)
    if len(matrix) != len(starts_array) or starts_array.shape != ends_array.shape:
        raise ValueError("Embeddings and window boundaries must have equal length")
    if not 1 <= k <= len(matrix):
        raise ValueError("k must be between one and the number of embeddings")

    order = np.lexsort((np.arange(len(matrix)), starts_array))
    centroid = l2_normalize(matrix.mean(axis=0))
    best: tuple[float, int, np.ndarray] | None = None
    for offset in range(0, len(order) - k + 1):
        block = order[offset : offset + k]
        block_starts = starts_array[block]
        block_ends = ends_array[block]
        gaps = block_starts[1:] - block_ends[:-1]
        if len(gaps) and np.any(np.abs(gaps) > gap_tolerance):
            continue
        try:
            score = float(aggregate_embeddings(matrix, block) @ centroid)
        except ValueError:
            # A perfectly cancelling block has no defined cosine direction.
            continue
        candidate = (-score, offset, np.sort(block).astype(np.int64))
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    if best is None:
        raise ValueError(f"No contiguous block of {k} windows is available")
    return best[2]


def enrollment_centroid(embeddings: np.ndarray) -> np.ndarray:
    matrix = l2_normalize(np.asarray(embeddings, dtype=np.float64), axis=1)
    if len(matrix) == 0:
        raise ValueError("Enrollment requires at least one embedding")
    return l2_normalize(matrix.mean(axis=0))


def score_against_enrollments(
    attack_embedding: np.ndarray,
    speaker: str,
    enrollments: dict[str, np.ndarray],
) -> dict[str, float]:
    """Return independent target score, strongest impostor and their margin."""
    if speaker not in enrollments:
        raise KeyError(f"Missing enrollment for speaker {speaker}")
    if len(enrollments) < 2:
        raise ValueError("At least two speakers are required for impostor scoring")
    attack = l2_normalize(np.asarray(attack_embedding, dtype=np.float64))
    normalized = {key: l2_normalize(value) for key, value in enrollments.items()}
    target = float(attack @ normalized[speaker])
    impostor = max(float(attack @ value) for key, value in normalized.items() if key != speaker)
    return {"target_score": target, "max_impostor_score": impostor, "margin": target - impostor}


def threshold_at_far(impostor_scores: Iterable[float], target_far: float) -> float:
    """Choose the lowest threshold whose empirical `score >= threshold` FAR fits."""
    scores = np.asarray(list(impostor_scores), dtype=np.float64)
    if scores.ndim != 1 or len(scores) == 0 or not np.all(np.isfinite(scores)):
        raise ValueError("A finite, nonempty impostor-score vector is required")
    if not 0 <= target_far < 1:
        raise ValueError("target_far must be in [0, 1)")
    for threshold in np.unique(scores):
        if float(np.mean(scores >= threshold)) <= target_far:
            return float(threshold)
    return float(np.nextafter(scores.max(), np.inf))
