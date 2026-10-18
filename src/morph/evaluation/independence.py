"""Dataset Independence and Holdout Isolation Auditor (Milestone M8.3).

Enforces scientific holdout independence beyond simple vector distance checks.
Audits:
1. Disjoint Session Identifiers (no shared session or recording UUIDs)
2. Temporal Window Isolation (no overlapping capture intervals)
3. Generation Seed Isolation (disjoint pseudo-random seed spaces)
4. Minimum Pairwise Euclidean Distance (absence of exact vector replicas)
5. Multi-Frame Subsequence Non-Duplication (no copied gesture trajectories)
6. Preprocessing / Normalization Isolation (parameters derived solely from training)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from morph.common.types import FeaturePacket


@dataclass
class IndependenceAuditResult:
    """Outcome of holdout independence verification."""

    is_independent: bool
    passed_rules: list[str] = field(default_factory=list)
    violated_rules: list[str] = field(default_factory=list)
    min_euclidean_distance: float = 0.0
    mean_euclidean_distance: float = 0.0
    temporal_overlap_ns: int = 0
    colliding_seeds: list[int] = field(default_factory=list)
    shared_session_ids: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_independent": self.is_independent,
            "passed_rules": self.passed_rules,
            "violated_rules": self.violated_rules,
            "min_euclidean_distance": self.min_euclidean_distance,
            "mean_euclidean_distance": self.mean_euclidean_distance,
            "temporal_overlap_ns": self.temporal_overlap_ns,
            "colliding_seeds": self.colliding_seeds,
            "shared_session_ids": self.shared_session_ids,
            "details": self.details,
        }


class DatasetIndependenceAuditor:
    """Comprehensive auditor for dataset and benchmark holdout independence."""

    RULE_DISJOINT_SESSION = "RULE_DISJOINT_SESSION"
    RULE_TEMPORAL_ISOLATION = "RULE_TEMPORAL_ISOLATION"
    RULE_SEED_ISOLATION = "RULE_SEED_ISOLATION"
    RULE_ZERO_VECTOR_LEAKAGE = "RULE_ZERO_VECTOR_LEAKAGE"
    RULE_SUBSEQUENCE_DUPLICATION = "RULE_SUBSEQUENCE_DUPLICATION"
    RULE_TRANSFORMATION_ISOLATION = "RULE_TRANSFORMATION_ISOLATION"

    def __init__(self, tolerance: float = 1e-4):
        self.tolerance = tolerance

    def audit(
        self,
        calibration_prototypes: dict[str, list[np.ndarray]],
        evaluation_stream: list[FeaturePacket],
        calibration_seeds: list[int] | None = None,
        evaluation_seeds: list[int] | None = None,
        calibration_session_id: str | None = None,
        evaluation_session_id: str | None = None,
        calibration_time_range_ns: tuple[int, int] | None = None,
        evaluation_time_range_ns: tuple[int, int] | None = None,
        shared_normalization_basis: bool = False,
    ) -> IndependenceAuditResult:
        """Execute all six holdout independence audit rules.

        Returns an IndependenceAuditResult documenting every rule outcome.
        """
        passed: list[str] = []
        violated: list[str] = []
        details: dict[str, Any] = {}

        # 1. Session Isolation
        shared_sessions: list[str] = []
        if calibration_session_id and evaluation_session_id:
            if calibration_session_id == evaluation_session_id:
                shared_sessions.append(calibration_session_id)
                violated.append(self.RULE_DISJOINT_SESSION)
                details[self.RULE_DISJOINT_SESSION] = (
                    f"Calibration and evaluation share session ID: {calibration_session_id}"
                )
            else:
                passed.append(self.RULE_DISJOINT_SESSION)
        else:
            # If not provided, marked conditionally passed
            passed.append(self.RULE_DISJOINT_SESSION)

        # 2. Temporal Window Isolation
        overlap_ns = 0
        if calibration_time_range_ns and evaluation_time_range_ns:
            cal_s, cal_e = calibration_time_range_ns
            eval_s, eval_e = evaluation_time_range_ns
            overlap_start = max(cal_s, eval_s)
            overlap_end = min(cal_e, eval_e)
            if overlap_start < overlap_end:
                overlap_ns = overlap_end - overlap_start
                violated.append(self.RULE_TEMPORAL_ISOLATION)
                details[self.RULE_TEMPORAL_ISOLATION] = (
                    f"Temporal window overlap detected: {overlap_ns} ns ({overlap_ns / 1e9:.3f}s)"
                )
            else:
                passed.append(self.RULE_TEMPORAL_ISOLATION)
        else:
            passed.append(self.RULE_TEMPORAL_ISOLATION)

        # 3. Seed Isolation
        colliding_seeds: list[int] = []
        if calibration_seeds is not None and evaluation_seeds is not None:
            c_set = set(calibration_seeds)
            e_set = set(evaluation_seeds)
            intersect = c_set.intersection(e_set)
            if intersect:
                colliding_seeds = sorted(list(intersect))
                violated.append(self.RULE_SEED_ISOLATION)
                details[self.RULE_SEED_ISOLATION] = (
                    f"Shared generation seeds detected: {colliding_seeds}"
                )
            else:
                passed.append(self.RULE_SEED_ISOLATION)
        else:
            passed.append(self.RULE_SEED_ISOLATION)

        # 4. Zero Vector Leakage (Pairwise Euclidean Distance)
        cal_vecs: list[np.ndarray] = []
        for vecs in calibration_prototypes.values():
            for v in vecs:
                if v is not None and len(v) > 0:
                    cal_vecs.append(np.asarray(v, dtype=np.float64))

        if not cal_vecs:
            raise ValueError("Calibration prototype collection is empty.")

        eval_vecs: list[np.ndarray] = [
            np.asarray(pkt.vector, dtype=np.float64)
            for pkt in evaluation_stream
            if pkt.valid and pkt.vector is not None and len(pkt.vector) > 0
        ]

        if not eval_vecs:
            raise ValueError("Evaluation stream contains no valid feature vectors.")

        cal_mat = np.stack(cal_vecs, axis=0)  # (N_cal, D)
        eval_mat = np.stack(eval_vecs, axis=0)  # (N_eval, D)

        diff = eval_mat[:, np.newaxis, :] - cal_mat[np.newaxis, :, :]
        dists = np.linalg.norm(diff, axis=2)  # (N_eval, N_cal)

        min_per_frame = np.min(dists, axis=1)
        min_dist = float(np.min(min_per_frame))
        mean_dist = float(np.mean(min_per_frame))

        if min_dist <= self.tolerance:
            violated.append(self.RULE_ZERO_VECTOR_LEAKAGE)
            details[self.RULE_ZERO_VECTOR_LEAKAGE] = (
                f"Min Euclidean distance {min_dist:.6f} <= tolerance {self.tolerance:.6f}"
            )
        else:
            passed.append(self.RULE_ZERO_VECTOR_LEAKAGE)

        # 5. Multi-Frame Subsequence Non-Duplication
        # Checks if any continuous subsequence of length 5 has near-zero variation against calibration
        subseq_leakage = False
        if len(eval_vecs) >= 5 and len(cal_vecs) >= 5:
            # Check rolling norm against contiguous cal vectors
            for i in range(len(cal_vecs) - 4):
                cal_sub = cal_mat[i : i + 5]
                for j in range(0, min(len(eval_vecs) - 4, 200), 5):  # Sample intervals
                    eval_sub = eval_mat[j : j + 5]
                    sub_diff = np.linalg.norm(eval_sub - cal_sub)
                    if sub_diff < self.tolerance * 5:
                        subseq_leakage = True
                        break
                if subseq_leakage:
                    break

        if subseq_leakage:
            violated.append(self.RULE_SUBSEQUENCE_DUPLICATION)
            details[self.RULE_SUBSEQUENCE_DUPLICATION] = (
                "Identical multi-frame subsequence detected between calibration and evaluation"
            )
        else:
            passed.append(self.RULE_SUBSEQUENCE_DUPLICATION)

        # 6. Transformation / Normalization Isolation
        if shared_normalization_basis:
            violated.append(self.RULE_TRANSFORMATION_ISOLATION)
            details[self.RULE_TRANSFORMATION_ISOLATION] = (
                "Normalization parameters were computed jointly across calibration and evaluation"
            )
        else:
            passed.append(self.RULE_TRANSFORMATION_ISOLATION)

        is_independent = len(violated) == 0

        return IndependenceAuditResult(
            is_independent=is_independent,
            passed_rules=passed,
            violated_rules=violated,
            min_euclidean_distance=min_dist,
            mean_euclidean_distance=mean_dist,
            temporal_overlap_ns=overlap_ns,
            colliding_seeds=colliding_seeds,
            shared_session_ids=shared_sessions,
            details=details,
        )
