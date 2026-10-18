"""Condition B: Personalized Prototype / KNN Recognizer with Unknown Rejection."""

from __future__ import annotations

import numpy as np

from morph.common.types import FeaturePacket, RecognitionResult


class PersonalizedRecognizerB:
    """Condition B: User-personalized prototype/centroid matching.

    Features:
    - Normalizes prototypes from user-enrolled samples.
    - Explicit rejection of unknown movements failing similarity threshold.
    - Explicit rejection of ambiguous movements failing separation margin.
    - In Condition B, fires immediately on first frame meeting criteria (no intention gate).
    """

    VERSION = "personalized-prototype-b-v1.0"

    def __init__(
        self,
        min_similarity: float = 0.65,
        min_margin: float = 0.15,
        profile_version: str = "profile-v1",
    ):
        self.min_similarity = min_similarity
        self.min_margin = min_margin
        self.profile_version = profile_version
        self.prototypes: dict[str, np.ndarray] = {}  # label -> normalized prototype vector

    def fit(self, training_data: dict[str, list[np.ndarray]]) -> None:
        """Fit class prototypes from enrolled sample vectors.

        Args:
            training_data: Mapping of gesture label to list of sample vectors (shape 32).
        """
        self.prototypes.clear()
        for label, samples in training_data.items():
            if not samples:
                continue
            arr = np.array(samples, dtype=np.float64)
            # Compute mean centroid
            mean_vec = np.mean(arr, axis=0)
            norm = np.linalg.norm(mean_vec)
            if norm > 1e-6:
                mean_vec = mean_vec / norm
            self.prototypes[label] = mean_vec

    def predict(self, packet: FeaturePacket) -> RecognitionResult:
        """Classify feature packet using cosine similarity against stored prototypes."""
        if not packet.valid or packet.vector is None:
            return RecognitionResult(
                frame_id=packet.frame_id,
                t_ns=packet.t_ns,
                label_scores={},
                best_label="UNKNOWN",
                second_label="UNKNOWN",
                accepted_candidate_or_none=None,
                reject_reason=packet.validity_reason or "INVALID_FEATURE_PACKET",
                recognizer_version=self.VERSION,
                profile_version=self.profile_version,
            )

        if not self.prototypes:
            return RecognitionResult(
                frame_id=packet.frame_id,
                t_ns=packet.t_ns,
                label_scores={},
                best_label="UNTRAINED",
                second_label="UNTRAINED",
                accepted_candidate_or_none=None,
                reject_reason="NO_TRAINED_PROTOTYPES_IN_PROFILE",
                recognizer_version=self.VERSION,
                profile_version=self.profile_version,
            )

        v = packet.vector
        v_norm = np.linalg.norm(v)

        # Check for near-zero motion (resting neutral)
        if v_norm < 0.05:
            return RecognitionResult(
                frame_id=packet.frame_id,
                t_ns=packet.t_ns,
                label_scores={k: 0.0 for k in self.prototypes},
                best_label="NEUTRAL",
                second_label="NEUTRAL",
                accepted_candidate_or_none=None,
                reject_reason="RESTING_NEUTRAL_MOTION_BELOW_ACTIVATION_FLOOR",
                recognizer_version=self.VERSION,
                profile_version=self.profile_version,
            )

        v_unit = v / v_norm

        # Compute cosine similarities
        scores: dict[str, float] = {}
        for label, proto in self.prototypes.items():
            sim = float(np.dot(v_unit, proto))
            scores[label] = max(0.0, sim)

        # Deterministic sorting: sort by score descending, then alphabetically by label to break ties safely
        sorted_candidates = sorted(scores.items(), key=lambda item: (-item[1], item[0]))

        best_label, best_score = sorted_candidates[0]
        second_label, second_score = (
            sorted_candidates[1] if len(sorted_candidates) > 1 else ("NONE", 0.0)
        )

        # 1. Unknown Rejection: Score must meet minimum similarity
        if best_score < self.min_similarity:
            return RecognitionResult(
                frame_id=packet.frame_id,
                t_ns=packet.t_ns,
                label_scores=scores,
                best_label=best_label,
                second_label=second_label,
                accepted_candidate_or_none=None,
                reject_reason=f"UNKNOWN_MOVEMENT_BELOW_SIMILARITY ({best_score:.2f} < {self.min_similarity:.2f})",
                recognizer_version=self.VERSION,
                profile_version=self.profile_version,
            )

        # 2. Ambiguity Margin Check: Delta between top 2 candidates must meet margin
        margin = best_score - second_score
        if len(sorted_candidates) > 1 and margin < self.min_margin:
            return RecognitionResult(
                frame_id=packet.frame_id,
                t_ns=packet.t_ns,
                label_scores=scores,
                best_label=best_label,
                second_label=second_label,
                accepted_candidate_or_none=None,
                reject_reason=f"AMBIGUOUS_CONFLICT_BETWEEN_CLASSES (Margin {margin:.2f} < {self.min_margin:.2f})",
                recognizer_version=self.VERSION,
                profile_version=self.profile_version,
            )

        # Both checks passed
        return RecognitionResult(
            frame_id=packet.frame_id,
            t_ns=packet.t_ns,
            label_scores=scores,
            best_label=best_label,
            second_label=second_label,
            accepted_candidate_or_none=best_label,
            reject_reason="",
            recognizer_version=self.VERSION,
            profile_version=self.profile_version,
        )

    def to_dict(self) -> dict[str, list[float]]:
        """Serialize prototype weights to JSON-compatible dictionary."""
        return {lbl: arr.tolist() for lbl, arr in self.prototypes.items()}

    def from_dict(self, data: dict[str, list[float]]) -> None:
        """Load prototype weights from dictionary."""
        self.prototypes = {lbl: np.array(vals, dtype=np.float64) for lbl, vals in data.items()}
