"""User-Specific Guided Parameter Calibration Engine (Milestone M8.4).

Provides evidence-based parameter tuning balancing:
- Intended gesture recall (sensitivity)
- Unintended false activations (specificity)
- Trigger latency (responsiveness)
- User physical effort & comfort (holding fatigue)

Includes strict non-medical disclaimers, multi-objective scoring,
insufficient/conflicting data detection, and atomic SQLite profile version rollback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from morph.common.config import RecognitionConfig
from morph.common.types import FeaturePacket, State
from morph.intent.engine import IntentEngine
from morph.recognition.recognizer_b import PersonalizedRecognizerB
from morph.storage.versions import ProfileVersion, ProfileVersionManager


class RecommendationStatus(str, Enum):
    """Classification of calibration recommendation confidence."""

    RECOMMENDED = "RECOMMENDED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CONFLICTING_DATA = "CONFLICTING_DATA"
    ALL_MISSED = "ALL_MISSED"
    EXCESSIVE_FALSE_ACTIVATIONS = "EXCESSIVE_FALSE_ACTIVATIONS"


@dataclass
class CalibrationSample:
    """A labeled sample sequence of feature packets recorded during calibration practice."""

    label: (
        str  # e.g., "Brow Raise", "Smile / Lip Corner Pull", "Chin Raise / Mouth Open", "NEUTRAL"
    )
    packets: list[FeaturePacket]
    start_ns: int
    end_ns: int
    is_intended: bool = True

    def __post_init__(self):
        if self.start_ns < 0 or self.end_ns < self.start_ns:
            raise ValueError(f"Invalid sample timestamp range: {self.start_ns} -> {self.end_ns}")


@dataclass(frozen=True)
class ParameterCandidate:
    """A parameter configuration candidate for evaluation."""

    hold_ms: int
    release_ms: int
    cooldown_ms: int
    min_similarity: float
    min_margin: float

    def to_config(self) -> RecognitionConfig:
        cfg = RecognitionConfig(
            hold_ms=self.hold_ms,
            release_ms=self.release_ms,
            cooldown_ms=self.cooldown_ms,
            min_similarity=self.min_similarity,
            min_margin=self.min_margin,
        )
        cfg.validate()
        return cfg

    def to_dict(self) -> dict[str, Any]:
        return {
            "hold_ms": self.hold_ms,
            "release_ms": self.release_ms,
            "cooldown_ms": self.cooldown_ms,
            "min_similarity": round(self.min_similarity, 3),
            "min_margin": round(self.min_margin, 3),
        }


@dataclass
class CandidateEvaluationResult:
    """Measured performance metrics for a single parameter candidate."""

    candidate: ParameterCandidate
    intended_recall: float
    false_activation_count: int
    false_activation_rate_per_hr: float
    mean_latency_ms: float
    comfort_score: float  # 0.0 to 1.0 (higher = easier to hold)
    composite_score: float  # Multi-objective weighted score
    is_viable: bool
    rejection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "intended_recall": round(self.intended_recall, 4),
            "false_activation_count": self.false_activation_count,
            "false_activation_rate_per_hr": round(self.false_activation_rate_per_hr, 2),
            "mean_latency_ms": round(self.mean_latency_ms, 2),
            "comfort_score": round(self.comfort_score, 4),
            "composite_score": round(self.composite_score, 4),
            "is_viable": self.is_viable,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class CalibrationRecommendation:
    """The synthesized outcome of guided calibration evaluation."""

    status: RecommendationStatus
    best_candidate: ParameterCandidate | None
    confidence: float
    evaluation_matrix: list[CandidateEvaluationResult] = field(default_factory=list)
    notes: str = ""
    disclaimer: str = (
        "NON-CLINICAL RESEARCH PROTOTYPE DISCLAIMER: Parameter calibration is an algorithmic "
        "optimization tool designed solely for interaction comfort. It does not provide medical, "
        "diagnostic, or assistive therapeutic certification."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "best_candidate": self.best_candidate.to_dict() if self.best_candidate else None,
            "confidence": round(self.confidence, 4),
            "evaluation_matrix": [c.to_dict() for c in self.evaluation_matrix],
            "notes": self.notes,
            "disclaimer": self.disclaimer,
        }


class UserParameterCalibrator:
    """Guides user-specific recognition parameter calibration, balancing recall, FA, latency, and comfort."""

    # Default permitted grid for guided calibration search
    DEFAULT_CANDIDATE_GRID: list[ParameterCandidate] = [
        # Conservative Default
        ParameterCandidate(300, 150, 300, 0.65, 0.15),
        # Responsive / Low Hold (for quick fatigue-sensitive users)
        ParameterCandidate(200, 150, 250, 0.60, 0.12),
        ParameterCandidate(250, 150, 300, 0.65, 0.15),
        # Sustained / High Confidence (for spasticity / involuntary twitch prone users)
        ParameterCandidate(400, 150, 350, 0.70, 0.15),
        ParameterCandidate(500, 200, 400, 0.70, 0.18),
        # Relaxed Thresholds (for subtle / low-amplitude movements)
        ParameterCandidate(300, 150, 300, 0.55, 0.10),
        # Strict Thresholds (for highly expressive faces)
        ParameterCandidate(300, 150, 300, 0.75, 0.20),
    ]

    def __init__(self, version_manager: ProfileVersionManager | None = None):
        self.version_manager = version_manager or ProfileVersionManager()

    def evaluate_parameter_grid(
        self,
        intended_samples: list[CalibrationSample],
        non_command_samples: list[CalibrationSample],
        recognizer: PersonalizedRecognizerB,
        candidate_grid: list[ParameterCandidate] | None = None,
    ) -> CalibrationRecommendation:
        """Evaluate parameter candidates against user calibration samples.

        Enforces data sufficiency and conflict checks before making recommendations.
        """
        grid = candidate_grid or self.DEFAULT_CANDIDATE_GRID

        # 1. Check data sufficiency (requires at least 3 intended samples and >= 1.0s non-command)
        total_non_cmd_ns = sum(s.end_ns - s.start_ns for s in non_command_samples)
        non_cmd_hours = (total_non_cmd_ns / 1e9) / 3600.0

        if len(intended_samples) < 3 or (total_non_cmd_ns / 1e9) < 1.0:
            return CalibrationRecommendation(
                status=RecommendationStatus.INSUFFICIENT_DATA,
                best_candidate=None,
                confidence=0.0,
                notes=(
                    f"Insufficient calibration data: {len(intended_samples)} intended samples (min 3) "
                    f"and {total_non_cmd_ns / 1e9:.2f}s non-command duration (min 1.0s). "
                    "Record additional samples before calibrating parameters."
                ),
            )

        # 2. Check for conflicting measurements (e.g. non-command sample triggers high similarity)
        conflicting_count = 0
        for nc_s in non_command_samples:
            for pkt in nc_s.packets:
                pred = recognizer.predict(pkt)
                score = pred.label_scores.get(pred.best_label, 0.0)
                if pred.accepted_candidate_or_none and score >= 0.85:
                    conflicting_count += 1

        if conflicting_count > 10:
            return CalibrationRecommendation(
                status=RecommendationStatus.CONFLICTING_DATA,
                best_candidate=None,
                confidence=0.0,
                notes=(
                    "Severe feature conflict detected: non-command facial movements repeatedly "
                    "matched intended gesture prototypes with high similarity. "
                    "Re-record baseline neutral pose and distinct gesture movements."
                ),
            )

        # 3. Simulate each candidate across samples
        eval_results: list[CandidateEvaluationResult] = []

        for cand in grid:
            # Validate candidate invariants
            try:
                cfg = cand.to_config()
            except ValueError as e:
                eval_results.append(
                    CandidateEvaluationResult(
                        candidate=cand,
                        intended_recall=0.0,
                        false_activation_count=999,
                        false_activation_rate_per_hr=9999.0,
                        mean_latency_ms=999.0,
                        comfort_score=0.0,
                        composite_score=0.0,
                        is_viable=False,
                        rejection_reason=f"Invariant violation: {e}",
                    )
                )
                continue

            rec_tuned = PersonalizedRecognizerB(
                min_similarity=cand.min_similarity,
                min_margin=cand.min_margin,
            )
            rec_tuned.prototypes = dict(recognizer.prototypes)

            action_mappings = {g: f"ACT_{g}" for g in recognizer.prototypes.keys()}

            # Test Intended Recall and Latency
            matched_intended = 0
            latencies_ms: list[float] = []

            for sample in intended_samples:
                engine = IntentEngine(config=cfg, action_mappings=action_mappings)
                engine.reset(State.IDLE)
                triggered = False
                trigger_time_ns = 0

                for pkt in sample.packets:
                    pred = rec_tuned.predict(pkt)
                    _, cmd, _ = engine.step(
                        recognition=pred,
                        tracking_valid=pkt.valid,
                        now_ns=pkt.t_ns,
                        mode="LIVE",
                        paused=False,
                    )
                    if cmd is not None and not triggered:
                        triggered = True
                        trigger_time_ns = cmd.confirmed_at_ns

                if triggered:
                    matched_intended += 1
                    lat_ms = (trigger_time_ns - sample.start_ns) / 1e6
                    latencies_ms.append(lat_ms)

            recall = matched_intended / len(intended_samples)
            mean_lat = (
                float(sum(latencies_ms) / len(latencies_ms)) if latencies_ms else cand.hold_ms
            )

            # Test False Activations on Non-Command Samples
            false_activations = 0
            for sample in non_command_samples:
                engine = IntentEngine(config=cfg, action_mappings=action_mappings)
                engine.reset(State.IDLE)
                for pkt in sample.packets:
                    pred = rec_tuned.predict(pkt)
                    _, cmd, _ = engine.step(
                        recognition=pred,
                        tracking_valid=pkt.valid,
                        now_ns=pkt.t_ns,
                        mode="LIVE",
                        paused=False,
                    )
                    if cmd is not None:
                        false_activations += 1

            fa_rate = (
                (false_activations / non_cmd_hours)
                if non_cmd_hours > 1e-6
                else float(false_activations)
            )

            # Comfort score: shorter holds are easier and less fatiguing for AAC users
            # 150ms -> 1.0 comfort, 600ms -> 0.55 comfort
            comfort = max(0.2, 1.0 - (cand.hold_ms - 150) / 1000.0)

            # Multi-objective composite score:
            # - Recall: 40%
            # - False activation suppression: 35%
            # - User comfort: 15%
            # - Trigger speed: 10%
            fa_penalty = min(1.0, false_activations * 0.5)
            lat_factor = max(0.0, 1.0 - (mean_lat / 1500.0))
            composite = (
                0.40 * recall + 0.35 * (1.0 - fa_penalty) + 0.15 * comfort + 0.10 * lat_factor
            )

            is_viable = (recall >= 0.60) and (false_activations <= 2)
            rejection_reason = ""
            if recall < 0.60:
                rejection_reason = f"Poor recall ({recall * 100:.1f}% < 60%)"
            elif false_activations > 2:
                rejection_reason = f"Excessive false activations ({false_activations} > 2)"

            eval_results.append(
                CandidateEvaluationResult(
                    candidate=cand,
                    intended_recall=recall,
                    false_activation_count=false_activations,
                    false_activation_rate_per_hr=fa_rate,
                    mean_latency_ms=mean_lat,
                    comfort_score=comfort,
                    composite_score=composite,
                    is_viable=is_viable,
                    rejection_reason=rejection_reason,
                )
            )

        # 4. Check global outcome classifications
        viable_candidates = [r for r in eval_results if r.is_viable]

        all_missed = all(r.intended_recall < 0.50 for r in eval_results)
        if all_missed:
            return CalibrationRecommendation(
                status=RecommendationStatus.ALL_MISSED,
                best_candidate=None,
                confidence=0.0,
                evaluation_matrix=eval_results,
                notes=(
                    "All evaluated parameter candidates failed to detect intended gestures. "
                    "The current facial prototypes may have been recorded with insufficient amplitude. "
                    "Retrain gesture classes in Studio with clear deliberate movements."
                ),
            )

        all_excessive_fa = all(r.false_activation_count > 3 for r in eval_results)
        if all_excessive_fa:
            return CalibrationRecommendation(
                status=RecommendationStatus.EXCESSIVE_FALSE_ACTIVATIONS,
                best_candidate=None,
                confidence=0.0,
                evaluation_matrix=eval_results,
                notes=(
                    "All parameter candidates produced excessive false activations on non-command data. "
                    "Ensure neutral baseline calibration was conducted in relaxed rest without talking."
                ),
            )

        if not viable_candidates:
            # Sort by composite score anyway for feedback
            sorted_all = sorted(eval_results, key=lambda x: x.composite_score, reverse=True)
            return CalibrationRecommendation(
                status=RecommendationStatus.CONFLICTING_DATA,
                best_candidate=sorted_all[0].candidate,
                confidence=0.30,
                evaluation_matrix=eval_results,
                notes="No candidate met both 60% recall and <= 2 false activations threshold.",
            )

        # Select highest composite score among viable candidates
        best = max(viable_candidates, key=lambda x: x.composite_score)

        return CalibrationRecommendation(
            status=RecommendationStatus.RECOMMENDED,
            best_candidate=best.candidate,
            confidence=float(best.composite_score),
            evaluation_matrix=eval_results,
            notes=(
                f"Optimal configuration identified: Hold={best.candidate.hold_ms}ms, "
                f"Release={best.candidate.release_ms}ms, Cooldown={best.candidate.cooldown_ms}ms, "
                f"Sim={best.candidate.min_similarity:.2f}, Margin={best.candidate.min_margin:.2f}. "
                f"Achieved {best.intended_recall * 100:.1f}% recall with {best.false_activation_count} false activations."
            ),
        )

    def store_candidate_version(
        self,
        profile_uuid: str,
        candidate: ParameterCandidate,
        recognizer: PersonalizedRecognizerB,
        neutral_landmarks: Any,
        interocular_ref: float,
        notes: str = "Candidate calibration evaluation",
    ) -> ProfileVersion:
        """Store candidate parameter set in SQLite with validation_status='CANDIDATE'."""
        thresholds = candidate.to_dict()
        action_mappings = {g: f"ACT_{g}" for g in recognizer.prototypes.keys()}

        # Serialize prototype weights
        weights: dict[str, list[list[float]]] = {}
        for g_name, vecs in recognizer.prototypes.items():
            weights[g_name] = [v.tolist() for v in vecs]

        return self.version_manager.create_version(
            profile_uuid=profile_uuid,
            weights=weights,
            thresholds=thresholds,
            gesture_mappings=action_mappings,
            neutral_landmarks=neutral_landmarks,
            interocular_ref=interocular_ref,
            validation_status="CANDIDATE",
            notes=notes,
        )

    def accept_candidate(
        self, profile_uuid: str, version_identifier: str | int
    ) -> ProfileVersion | None:
        """Promote candidate version to active VALIDATED status."""
        if isinstance(version_identifier, str):
            row = self.version_manager.db.fetch_one(
                "SELECT version_number FROM profile_versions WHERE profile_uuid = ? AND version_uuid = ?;",
                (profile_uuid, version_identifier),
            )
            if not row:
                raise KeyError(
                    f"Version UUID {version_identifier} not found for profile {profile_uuid}"
                )
            v_num = int(row["version_number"])
        else:
            v_num = version_identifier
        return self.version_manager.promote_candidate(profile_uuid, v_num)

    def reject_candidate(self, profile_uuid: str, version_identifier: str | int) -> None:
        """Mark candidate version as DEPRECATED."""
        with self.version_manager.db.get_connection() as conn:
            if isinstance(version_identifier, str):
                conn.execute(
                    "UPDATE profile_versions SET validation_status = 'DEPRECATED' WHERE profile_uuid = ? AND version_uuid = ?;",
                    (profile_uuid, version_identifier),
                )
            else:
                conn.execute(
                    "UPDATE profile_versions SET validation_status = 'DEPRECATED' WHERE profile_uuid = ? AND version_number = ?;",
                    (profile_uuid, version_identifier),
                )
            conn.commit()

    def rollback(self, profile_uuid: str, target_version_number: int) -> ProfileVersion | None:
        """Roll back active profile configuration to a prior validated version."""
        return self.version_manager.rollback_to_version(profile_uuid, target_version_number)
