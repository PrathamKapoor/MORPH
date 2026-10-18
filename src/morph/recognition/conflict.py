"""Gesture conflict and ambiguity detection service for MORPH 2.0 (PRD A06 / M5.1).

Detects overlapping facial gesture trajectories before active command execution,
categorizes collision severity, and provides actionable, user-interpretable guidance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class ConflictSeverity(str, Enum):
    """Categorical conflict severity between personalized gesture templates."""

    NONE = "NONE"
    POTENTIAL = "POTENTIAL"
    STRONG = "STRONG"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ConflictReport:
    """Detailed collision report for a candidate gesture against existing templates."""

    candidate_label: str
    conflicting_label: str | None
    severity: ConflictSeverity
    similarity: float
    euclidean_distance: float
    explanation: str
    recommendation: str
    safe_to_activate: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_label": self.candidate_label,
            "conflicting_label": self.conflicting_label,
            "severity": self.severity.value,
            "similarity": round(self.similarity, 4),
            "euclidean_distance": round(self.euclidean_distance, 4),
            "explanation": self.explanation,
            "recommendation": self.recommendation,
            "safe_to_activate": self.safe_to_activate,
        }


class GestureConflictDetector:
    """Analyzes stored and candidate gesture prototypes for geometric/blendshape collision."""

    STRONG_SIMILARITY_THRESHOLD = 0.85
    POTENTIAL_SIMILARITY_THRESHOLD = 0.70
    MIN_REQUIRED_SAMPLES = 3
    EXPECTED_FEATURE_DIM = 32

    def __init__(
        self,
        strong_threshold: float = STRONG_SIMILARITY_THRESHOLD,
        potential_threshold: float = POTENTIAL_SIMILARITY_THRESHOLD,
        min_samples: int = MIN_REQUIRED_SAMPLES,
    ):
        if not (0.0 < potential_threshold < strong_threshold <= 1.0):
            raise ValueError(
                f"Invalid thresholds: must satisfy 0 < potential ({potential_threshold}) < strong ({strong_threshold}) <= 1.0"
            )
        self.strong_threshold = strong_threshold
        self.potential_threshold = potential_threshold
        self.min_samples = min_samples

    def compute_prototype(self, samples: list[np.ndarray]) -> np.ndarray | None:
        """Validate sample array and compute L2-normalized mean prototype vector.

        Returns None if samples are insufficient or invalid.
        """
        if not samples or len(samples) < self.min_samples:
            return None

        clean_samples: list[np.ndarray] = []
        for s in samples:
            if not isinstance(s, np.ndarray):
                continue
            if s.shape != (self.EXPECTED_FEATURE_DIM,):
                continue
            if not np.all(np.isfinite(s)):
                continue
            clean_samples.append(s.astype(np.float64))

        if len(clean_samples) < self.min_samples:
            return None

        arr = np.array(clean_samples, dtype=np.float64)
        mean_vec = np.mean(arr, axis=0)
        norm = float(np.linalg.norm(mean_vec))
        if norm < 1e-7:
            return None
        return mean_vec / norm

    def check_conflict(
        self,
        candidate_label: str,
        candidate_samples: list[np.ndarray] | np.ndarray,
        existing_prototypes: dict[str, np.ndarray],
    ) -> ConflictReport:
        """Evaluate a new gesture candidate against existing stored gesture prototypes."""
        if isinstance(candidate_samples, np.ndarray):
            if candidate_samples.shape == (self.EXPECTED_FEATURE_DIM,) and np.all(
                np.isfinite(candidate_samples)
            ):
                norm = float(np.linalg.norm(candidate_samples))
                candidate_proto = (candidate_samples / norm) if norm > 1e-7 else None
            else:
                candidate_proto = None
        else:
            candidate_proto = self.compute_prototype(candidate_samples)

        if candidate_proto is None:
            return ConflictReport(
                candidate_label=candidate_label,
                conflicting_label=None,
                severity=ConflictSeverity.INSUFFICIENT_DATA,
                similarity=0.0,
                euclidean_distance=float("inf"),
                explanation=f"Insufficient valid samples ({len(candidate_samples) if isinstance(candidate_samples, list) else 0}) to compute a reliable prototype for '{candidate_label}'.",
                recommendation=f"Record at least {self.min_samples} clean, non-zero facial movement samples without rapid head motion.",
                safe_to_activate=False,
            )

        # Filter out self if present in existing prototypes
        other_prototypes = {k: v for k, v in existing_prototypes.items() if k != candidate_label}

        if not other_prototypes:
            return ConflictReport(
                candidate_label=candidate_label,
                conflicting_label=None,
                severity=ConflictSeverity.NONE,
                similarity=0.0,
                euclidean_distance=2.0,
                explanation=f"No other gesture prototypes currently enrolled for comparison. '{candidate_label}' is the first active gesture.",
                recommendation="Safe to activate. Proceed to enroll additional distinct facial movements if desired.",
                safe_to_activate=True,
            )

        max_sim = -1.0
        min_dist = float("inf")
        worst_conflicting_label: str | None = None

        for label, proto in other_prototypes.items():
            if (
                not isinstance(proto, np.ndarray)
                or proto.shape != (self.EXPECTED_FEATURE_DIM,)
                or not np.all(np.isfinite(proto))
            ):
                continue

            proto_norm = float(np.linalg.norm(proto))
            if proto_norm < 1e-7:
                continue
            unit_proto = proto / proto_norm

            sim = float(np.dot(candidate_proto, unit_proto))
            dist = float(np.linalg.norm(candidate_proto - unit_proto))

            if sim > max_sim:
                max_sim = sim
                min_dist = dist
                worst_conflicting_label = label

        if worst_conflicting_label is None:
            return ConflictReport(
                candidate_label=candidate_label,
                conflicting_label=None,
                severity=ConflictSeverity.NONE,
                similarity=0.0,
                euclidean_distance=2.0,
                explanation="No valid existing prototypes found for comparison.",
                recommendation="Safe to activate.",
                safe_to_activate=True,
            )

        if max_sim >= self.strong_threshold:
            severity = ConflictSeverity.STRONG
            explanation = (
                f"Movement '{candidate_label}' has very high feature overlap with existing gesture "
                f"'{worst_conflicting_label}' (cosine similarity {max_sim:.2f} >= {self.strong_threshold:.2f}). "
                "The recognizer will frequently misclassify or reject these movements as ambiguous."
            )
            recommendation = (
                f"Choose a clearly distinct facial or head movement for '{candidate_label}' "
                f"(e.g., mouth opening vs. eyebrow raise), or re-record with higher movement intensity."
            )
            safe = False
        elif max_sim >= self.potential_threshold:
            severity = ConflictSeverity.POTENTIAL
            explanation = (
                f"Movement '{candidate_label}' has moderate similarity to '{worst_conflicting_label}' "
                f"(cosine similarity {max_sim:.2f} >= {self.potential_threshold:.2f}). "
                "While distinguishable, subtle movements may trigger ambiguity rejections during operation."
            )
            recommendation = "Test both gestures in Practice Mode to confirm reliability before enabling live communication."
            safe = True
        else:
            severity = ConflictSeverity.NONE
            explanation = (
                f"Movement '{candidate_label}' is well separated from all other gestures "
                f"(maximum similarity to '{worst_conflicting_label}' is {max_sim:.2f} < {self.potential_threshold:.2f})."
            )
            recommendation = "Safe to activate. Proceed to practice or live communication board."
            safe = True

        return ConflictReport(
            candidate_label=candidate_label,
            conflicting_label=worst_conflicting_label,
            severity=severity,
            similarity=max_sim,
            euclidean_distance=min_dist,
            explanation=explanation,
            recommendation=recommendation,
            safe_to_activate=safe,
        )

    def check_all_pairs(self, prototypes: dict[str, np.ndarray]) -> list[ConflictReport]:
        """Check all pairwise combinations of stored gesture prototypes."""
        reports: list[ConflictReport] = []
        labels = list(prototypes.keys())
        for i, l1 in enumerate(labels):
            p1 = prototypes[l1]
            for l2 in labels[i + 1 :]:
                p2 = prototypes[l2]
                rep = self.check_conflict(
                    candidate_label=l1,
                    candidate_samples=p1,
                    existing_prototypes={l2: p2},
                )
                reports.append(rep)
        return reports
