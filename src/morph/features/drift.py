"""Calibration health check and feature distribution drift detector (PRD D03, D04 / M5.2).

Detects displacement from stored resting neutral baselines and prototype overlap
caused by camera placement or seating changes, providing actionable guidance
without making medical inferences or clinical diagnoses.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np


class CalibrationStatus(str, Enum):
    """Categorical calibration health status across sessions."""

    STABLE = "STABLE"
    MODERATE_DRIFT = "MODERATE_DRIFT"
    SEVERE_DRIFT = "SEVERE_DRIFT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INCOMPATIBLE_SCHEMA = "INCOMPATIBLE_SCHEMA"


@dataclass(frozen=True)
class CalibrationHealthReport:
    """Diagnostic report comparing current observations against stored calibration data."""

    status: CalibrationStatus
    baseline_drift: float
    max_gesture_overlap: float
    sample_count: int
    explanation: str
    recommendation: str
    requires_recalibration: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "baseline_drift": round(self.baseline_drift, 4),
            "max_gesture_overlap": round(self.max_gesture_overlap, 4),
            "sample_count": self.sample_count,
            "explanation": self.explanation,
            "recommendation": self.recommendation,
            "requires_recalibration": self.requires_recalibration,
        }


class DriftDetector:
    """Measures resting posture shift and prototype collision without medical claims."""

    DRIFT_THRESHOLD_MODERATE = 0.08  # 8% of interocular distance
    DRIFT_THRESHOLD_SEVERE = 0.16  # 16% of interocular distance
    NEUTRAL_GESTURE_OVERLAP_THRESHOLD = 0.50  # Cosine similarity threshold
    MIN_REQUIRED_FRAMES = 5

    def __init__(
        self,
        moderate_threshold: float = DRIFT_THRESHOLD_MODERATE,
        severe_threshold: float = DRIFT_THRESHOLD_SEVERE,
        gesture_overlap_threshold: float = NEUTRAL_GESTURE_OVERLAP_THRESHOLD,
        min_frames: int = MIN_REQUIRED_FRAMES,
    ):
        if not (0.0 < moderate_threshold < severe_threshold):
            raise ValueError("Must satisfy 0 < moderate_threshold < severe_threshold")
        self.moderate_threshold = moderate_threshold
        self.severe_threshold = severe_threshold
        self.gesture_overlap_threshold = gesture_overlap_threshold
        self.min_frames = min_frames

    def assess_neutral_drift(
        self,
        current_neutral_landmarks: list[np.ndarray] | np.ndarray,
        stored_neutral_landmarks: np.ndarray,
        interocular_ref: float,
        stored_prototypes: dict[str, np.ndarray] | None = None,
        feature_extractor: Any = None,
    ) -> CalibrationHealthReport:
        """Compare observed resting neutral landmarks against the stored neutral baseline.

        Args:
            current_neutral_landmarks: Array of (478, 3) or list of landmark arrays.
            stored_neutral_landmarks: Saved neutral landmark coordinates shape (478, 3).
            interocular_ref: Baseline interocular distance (anatomical scale).
            stored_prototypes: Optional trained gesture prototype vectors.
            feature_extractor: Optional FeatureExtractor to extract vectors for overlap check.
        """
        # Validate stored inputs
        if (
            not isinstance(stored_neutral_landmarks, np.ndarray)
            or stored_neutral_landmarks.shape != (478, 3)
            or not np.all(np.isfinite(stored_neutral_landmarks))
        ):
            return CalibrationHealthReport(
                status=CalibrationStatus.INSUFFICIENT_DATA,
                baseline_drift=float("inf"),
                max_gesture_overlap=0.0,
                sample_count=0,
                explanation="Stored neutral baseline is missing or corrupted.",
                recommendation="Perform a full neutral baseline calibration.",
                requires_recalibration=True,
            )

        if interocular_ref <= 1e-4:
            return CalibrationHealthReport(
                status=CalibrationStatus.INSUFFICIENT_DATA,
                baseline_drift=float("inf"),
                max_gesture_overlap=0.0,
                sample_count=0,
                explanation="Stored anatomical reference scale is invalid.",
                recommendation="Perform a full neutral baseline calibration.",
                requires_recalibration=True,
            )

        # Validate current observed inputs
        valid_frames: list[np.ndarray] = []
        if isinstance(current_neutral_landmarks, np.ndarray):
            if current_neutral_landmarks.ndim == 2 and current_neutral_landmarks.shape == (478, 3):
                if np.all(np.isfinite(current_neutral_landmarks)):
                    valid_frames.append(current_neutral_landmarks)
            elif current_neutral_landmarks.ndim == 3 and current_neutral_landmarks.shape[1:] == (
                478,
                3,
            ):
                for f in current_neutral_landmarks:
                    if np.all(np.isfinite(f)):
                        valid_frames.append(f)
        elif isinstance(current_neutral_landmarks, list):
            for f in current_neutral_landmarks:
                if isinstance(f, np.ndarray) and f.shape == (478, 3) and np.all(np.isfinite(f)):
                    valid_frames.append(f)

        if len(valid_frames) < self.min_frames:
            return CalibrationHealthReport(
                status=CalibrationStatus.INSUFFICIENT_DATA,
                baseline_drift=0.0,
                max_gesture_overlap=0.0,
                sample_count=len(valid_frames),
                explanation=f"Insufficient stable frames collected ({len(valid_frames)} < {self.min_frames}) for cross-session calibration verification.",
                recommendation="Look naturally at the camera while holding resting posture for 1–2 seconds.",
                requires_recalibration=False,
            )

        # 1. Compute median observed landmarks
        stack = np.stack(valid_frames, axis=0)  # (N, 478, 3)
        obs_median = np.median(stack, axis=0)  # (478, 3)

        # 2. Compute normalized landmark displacement relative to interocular distance
        # Focus on stable facial contour and ocular landmarks (e.g., nose tip 1, oculars 33, 263, 133, 362)
        key_landmarks = [1, 33, 133, 263, 362, 61, 291, 10, 152]
        shifts = np.linalg.norm(
            obs_median[key_landmarks] - stored_neutral_landmarks[key_landmarks], axis=1
        )
        mean_shift = float(np.mean(shifts))
        normalized_drift = mean_shift / interocular_ref

        # 3. Check for neutral-gesture overlap if prototypes and extractor provided
        max_overlap = 0.0
        overlapping_gesture: str | None = None
        if stored_prototypes and feature_extractor is not None:
            from morph.common.types import LandmarkPacket

            pkt = LandmarkPacket(
                frame_id=0,
                t_ns=0,
                face_count=1,
                normalized_landmarks=obs_median,
                valid=True,
            )
            feat = feature_extractor.extract(pkt)
            if feat.valid and feat.vector is not None:
                norm_v = float(np.linalg.norm(feat.vector))
                if norm_v > 1e-6:
                    unit_v = feat.vector / norm_v
                    for g_name, g_proto in stored_prototypes.items():
                        g_norm = float(np.linalg.norm(g_proto))
                        if g_norm > 1e-6:
                            sim = float(np.dot(unit_v, g_proto / g_norm))
                            if sim > max_overlap:
                                max_overlap = sim
                                overlapping_gesture = g_name

        # 4. Classify status
        if (
            normalized_drift >= self.severe_threshold
            or max_overlap >= self.gesture_overlap_threshold
        ):
            status = CalibrationStatus.SEVERE_DRIFT
            overlap_text = (
                f" Furthermore, current rest posture resembles '{overlapping_gesture}' (similarity: {max_overlap:.2f})."
                if overlapping_gesture and max_overlap >= self.gesture_overlap_threshold
                else ""
            )
            explanation = (
                f"Significant change detected in camera placement, seated distance, or head posture "
                f"(displacement ratio: {normalized_drift:.2f} >= {self.severe_threshold:.2f}).{overlap_text}"
            )
            recommendation = (
                "Seated posture or camera angle has shifted significantly. "
                "Reposition camera/chair or perform a 3-second quick recalibration before continuing."
            )
            requires_recal = True
        elif normalized_drift >= self.moderate_threshold:
            status = CalibrationStatus.MODERATE_DRIFT
            explanation = (
                f"Moderate change detected in camera angle or head orientation "
                f"(displacement ratio: {normalized_drift:.2f} >= {self.moderate_threshold:.2f})."
            )
            recommendation = (
                "Mild posture difference detected. You may continue, or run a quick recalibration "
                "if gestures feel less responsive than expected."
            )
            requires_recal = False
        else:
            status = CalibrationStatus.STABLE
            explanation = (
                f"Current resting posture closely matches the saved calibration baseline "
                f"(displacement ratio: {normalized_drift:.2f} < {self.moderate_threshold:.2f})."
            )
            recommendation = "Calibration is stable. System is ready for communication."
            requires_recal = False

        return CalibrationHealthReport(
            status=status,
            baseline_drift=normalized_drift,
            max_gesture_overlap=max_overlap,
            sample_count=len(valid_frames),
            explanation=explanation,
            recommendation=recommendation,
            requires_recalibration=requires_recal,
        )
