"""Evaluation session validity checking and benchmark admission gating (Milestone M8.2).

Enforces scientific integrity by ensuring:
- Timestamp monotonicity and strictly positive non-inverted intervals
- Valid source labels and enrolled gesture compatibility
- No accidental temporal overlap of mutually exclusive ground-truth events
- No training/test data leakage between enrollment and evaluation streams
- Quantified non-command exposure time and tracking-invalid duration
- Informed consent verification
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from morph.common.types import GroundTruthLabelType
from morph.evaluation.session import EvaluationSession


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of an evaluation session integrity audit."""

    is_valid: bool
    participant_id: str
    session_id: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_exposure_sec: float = 0.0
    non_command_exposure_sec: float = 0.0
    intended_command_count: int = 0
    tracking_invalid_sec: float = 0.0
    exclusion_code: str | None = None


class EvaluationSessionValidator:
    """Rigorous audit engine gating session admission into official research benchmarks."""

    def __init__(
        self,
        min_gesture_duration_ms: float = 50.0,
        max_gesture_duration_ms: float = 10_000.0,
        max_tracking_invalid_ratio: float = 0.50,
    ) -> None:
        self.min_gesture_duration_ms = min_gesture_duration_ms
        self.max_gesture_duration_ms = max_gesture_duration_ms
        self.max_tracking_invalid_ratio = max_tracking_invalid_ratio

    def validate_session(
        self,
        session: EvaluationSession,
        enrolled_gestures: set[str] | list[str] | None = None,
        profile_training_samples: list[np.ndarray] | None = None,
    ) -> ValidationResult:
        """Execute complete integrity audit on an evaluation session."""
        errors: list[str] = []
        warnings: list[str] = []
        exclusion_code: str | None = None

        # 1. Informed Consent Verification
        if not session.consented:
            errors.append("Informed consent is PENDING or NOT GRANTED. Session cannot be included.")
            exclusion_code = "EXCL_NO_CONSENT"
            return ValidationResult(
                is_valid=False,
                participant_id=session.participant_id,
                session_id=session.session_uuid,
                errors=errors,
                exclusion_code=exclusion_code,
            )

        # 2. Timestamp Ordering and Boundaries for Ground Truth Events
        sorted_events = sorted(session.ground_truth_events, key=lambda e: e.start_ns)
        for i, evt in enumerate(sorted_events):
            if evt.start_ns < 0 or evt.end_ns < 0:
                errors.append(
                    f"Event {evt.event_uuid or i} has negative timestamps: ({evt.start_ns}, {evt.end_ns})"
                )
                exclusion_code = exclusion_code or "EXCL_INVALID_TIMESTAMPS"

            if evt.end_ns <= evt.start_ns:
                errors.append(
                    f"Event {evt.event_uuid or i} has non-positive duration: start={evt.start_ns}, end={evt.end_ns}"
                )
                exclusion_code = exclusion_code or "EXCL_INVALID_TIMESTAMPS"

            dur_ms = (evt.end_ns - evt.start_ns) / 1_000_000.0
            if dur_ms < self.min_gesture_duration_ms:
                warnings.append(
                    f"Event {evt.event_uuid or i} ({evt.label}) is unusually brief ({dur_ms:.1f}ms < {self.min_gesture_duration_ms}ms)"
                )
            elif dur_ms > self.max_gesture_duration_ms:
                warnings.append(
                    f"Event {evt.event_uuid or i} ({evt.label}) is unusually long ({dur_ms:.1f}ms > {self.max_gesture_duration_ms}ms)"
                )

        # 3. Check for Accidental Overlap of Mutually Exclusive Events
        for i in range(len(sorted_events) - 1):
            curr_evt = sorted_events[i]
            next_evt = sorted_events[i + 1]
            if curr_evt.end_ns > next_evt.start_ns:
                overlap_ms = (curr_evt.end_ns - next_evt.start_ns) / 1_000_000.0
                errors.append(
                    f"Temporal overlap of {overlap_ms:.1f}ms between event '{curr_evt.label}' and '{next_evt.label}'"
                )
                exclusion_code = exclusion_code or "EXCL_LABEL_OVERLAP"

        # 4. Gesture Class Compatibility
        enrolled_set = set(enrolled_gestures) if enrolled_gestures else None
        intended_count = 0
        for evt in session.ground_truth_events:
            if evt.label_type in (
                GroundTruthLabelType.CORRECT_GESTURE.value,
                GroundTruthLabelType.INCORRECT_GESTURE.value,
            ):
                intended_count += 1
                if enrolled_set and evt.label not in enrolled_set:
                    errors.append(
                        f"Ground truth event label '{evt.label}' is not in enrolled profile gestures {enrolled_set}"
                    )
                    exclusion_code = exclusion_code or "EXCL_UNKNOWN_GESTURE"

        # 5. Data Leakage Verification
        if profile_training_samples and session.recorded_features:
            for feat_idx, feat in enumerate(session.recorded_features):
                if feat.vector is None:
                    continue
                v_feat = np.array(feat.vector, dtype=np.float64)
                for tr_idx, tr_sample in enumerate(profile_training_samples):
                    dist = float(np.linalg.norm(v_feat - tr_sample))
                    if dist < 1e-6:
                        errors.append(
                            f"Train/test data leakage detected: Feature frame {feat_idx} is identical to enrollment sample {tr_idx} (dist={dist:.2e})"
                        )
                        exclusion_code = exclusion_code or "EXCL_TRAIN_TEST_LEAKAGE"
                        break
                if exclusion_code == "EXCL_TRAIN_TEST_LEAKAGE":
                    break

        # 6. Exposure Duration & Tracking Loss Accounting
        total_exposure_sec = 0.0
        tracking_invalid_sec = 0.0

        if session.recorded_features:
            t0 = session.recorded_features[0].t_ns
            t1 = session.recorded_features[-1].t_ns
            total_exposure_sec = max(0.0, (t1 - t0) / 1_000_000_000.0)

            # Count invalid frames
            invalid_frames = sum(
                1 for f in session.recorded_features if not getattr(f, "tracking_valid", True)
            )
            if len(session.recorded_features) > 0 and total_exposure_sec > 0:
                tracking_invalid_sec = total_exposure_sec * (
                    invalid_frames / len(session.recorded_features)
                )

        elif session.ground_truth_events:
            # Fallback to ground truth bounds if features not streamed to session
            t0 = sorted_events[0].start_ns
            t1 = sorted_events[-1].end_ns
            total_exposure_sec = max(0.0, (t1 - t0) / 1_000_000_000.0)

        # Compute merged intended duration
        intended_intervals = [
            (e.start_ns, e.end_ns)
            for e in sorted_events
            if e.label_type
            in (
                GroundTruthLabelType.CORRECT_GESTURE.value,
                GroundTruthLabelType.INCORRECT_GESTURE.value,
            )
        ]
        intended_duration_sec = self._compute_merged_interval_duration_sec(intended_intervals)
        non_command_exposure_sec = max(0.0, total_exposure_sec - intended_duration_sec)

        if total_exposure_sec <= 0 and (session.recorded_features or session.ground_truth_events):
            errors.append("Total session exposure duration is non-positive.")
            exclusion_code = exclusion_code or "EXCL_ZERO_EXPOSURE"

        if total_exposure_sec > 0:
            invalid_ratio = tracking_invalid_sec / total_exposure_sec
            if invalid_ratio > self.max_tracking_invalid_ratio:
                warnings.append(
                    f"High tracking invalid exposure ({invalid_ratio * 100:.1f}% > {self.max_tracking_invalid_ratio * 100:.1f}%)"
                )

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            participant_id=session.participant_id,
            session_id=session.session_uuid,
            errors=errors,
            warnings=warnings,
            total_exposure_sec=round(total_exposure_sec, 3),
            non_command_exposure_sec=round(non_command_exposure_sec, 3),
            intended_command_count=intended_count,
            tracking_invalid_sec=round(tracking_invalid_sec, 3),
            exclusion_code=exclusion_code,
        )

    def _compute_merged_interval_duration_sec(self, intervals: list[tuple[int, int]]) -> float:
        """Merge overlapping or contiguous nanosecond intervals and return total seconds."""
        if not intervals:
            return 0.0

        sorted_ints = sorted(intervals, key=lambda x: x[0])
        merged = [sorted_ints[0]]

        for start, end in sorted_ints[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))

        total_ns = sum(end - start for start, end in merged)
        return total_ns / 1_000_000_000.0
