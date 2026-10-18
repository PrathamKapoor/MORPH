"""Fair, synchronous A/B/C baseline replay and ablation evaluation engine (PRD E03, E04, E05, E09 / M5.4).

Guarantees:
- Condition A, B, and C process the exact identical stream of FeaturePackets.
- Condition B and Condition C evaluate bit-exact identical classifier scores per frame.
- Condition B uses a fair, conventional debounced/release-to-rearm event trigger
  (does NOT fire on every frame, eliminating artificial baseline degradation).
- Full ablation suite isolating hold duration, release dwell, and ambiguity margin.
- Zero side-effects or external action dispatches during replay.
"""

from __future__ import annotations

from typing import Any

from morph.common.config import RecognitionConfig
from morph.common.types import FeaturePacket, GroundTruthEvent, State
from morph.evaluation.matching import match_events_one_to_one
from morph.evaluation.metrics import (
    calculate_benchmark_metrics,
    compute_merged_interval_duration_sec,
)
from morph.intent.engine import IntentEngine
from morph.recognition.recognizer_a import BaselineRecognizerA
from morph.recognition.recognizer_b import PersonalizedRecognizerB


class ConventionalDebouncedDispatcher:
    """Conventional event trigger implementing standard debounce/release-to-rearm.

    Fires exactly once when a candidate crosses threshold from neutral,
    and suppresses re-triggering until the user releases below threshold.
    """

    def __init__(self, action_mapping: dict[str, str]):
        self.action_mapping = action_mapping
        self._active_candidate: str | None = None

    def reset(self) -> None:
        self._active_candidate = None

    def step(self, candidate: str | None, t_ns: int) -> tuple[str, int] | None:
        if candidate is None or candidate == "NEUTRAL":
            self._active_candidate = None
            return None

        if self._active_candidate is None:
            # Onset trigger
            self._active_candidate = candidate
            action = self.action_mapping.get(candidate, candidate)
            return (action, t_ns)

        if candidate != self._active_candidate:
            # Gesture switched abruptly
            self._active_candidate = candidate
            action = self.action_mapping.get(candidate, candidate)
            return (action, t_ns)

        # Candidate is held: suppress duplicate firing
        return None


class ReplayEngine:
    """Fair, reproducible research replay engine with ablations."""

    def __init__(
        self,
        config: RecognitionConfig | None = None,
        rec_a: BaselineRecognizerA | None = None,
        rec_b: PersonalizedRecognizerB | None = None,
    ):
        self.config = config or RecognitionConfig()
        self.rec_a = rec_a or BaselineRecognizerA()
        self.rec_b = rec_b or PersonalizedRecognizerB(
            min_similarity=self.config.min_similarity,
            min_margin=self.config.min_margin,
        )

    def run_replay(
        self,
        feature_stream: list[FeaturePacket],
        ground_truth_events: list[GroundTruthEvent],
        session_duration_sec: float | None = None,
        is_synthetic: bool = False,
        dataset_version: str = "eval-stream-v2.0",
    ) -> dict[str, Any]:
        """Execute full fair replay across Condition A, B, C, and ablations."""
        action_mapping = {
            "Brow Raise": "NEXT_TILE",
            "Smile / Lip Corner Pull": "SELECT_TILE",
            "Chin Raise / Mouth Open": "PREVIOUS_TILE",
        }

        # Compute disjoint intended duration, properly merging any overlapping ground truth intervals
        gt_intervals = [(gt.start_ns, gt.end_ns) for gt in ground_truth_events]
        total_intended_duration_sec = compute_merged_interval_duration_sec(gt_intervals)

        if session_duration_sec is None:
            if feature_stream:
                session_duration_sec = (
                    feature_stream[-1].t_ns - feature_stream[0].t_ns
                ) / 1_000_000_000.0
            else:
                session_duration_sec = 0.0

        # Setup dispatchers and engines
        debouncer_a = ConventionalDebouncedDispatcher(action_mapping)
        debouncer_b = ConventionalDebouncedDispatcher(action_mapping)

        engine_c = IntentEngine(config=self.config, action_mappings=action_mapping)
        engine_c.reset(State.IDLE)

        # Ablation 1: No Hold Time (hold_ms = 0)
        config_no_hold = RecognitionConfig(
            hold_ms=0,
            release_ms=self.config.release_ms,
            cooldown_ms=self.config.cooldown_ms,
            min_similarity=self.config.min_similarity,
            min_margin=self.config.min_margin,
        )
        engine_no_hold = IntentEngine(config=config_no_hold, action_mappings=action_mapping)
        engine_no_hold.reset(State.IDLE)

        # Ablation 2: No Release Dwell (release_ms = 0)
        config_no_rel = RecognitionConfig(
            hold_ms=self.config.hold_ms,
            release_ms=0,
            cooldown_ms=self.config.cooldown_ms,
            min_similarity=self.config.min_similarity,
            min_margin=self.config.min_margin,
        )
        engine_no_rel = IntentEngine(config=config_no_rel, action_mappings=action_mapping)
        engine_no_rel.reset(State.IDLE)

        # Ablation 3: No Ambiguity Margin (min_margin = 0.0)
        rec_b_no_margin = PersonalizedRecognizerB(
            min_similarity=self.config.min_similarity,
            min_margin=0.0,
        )
        rec_b_no_margin.prototypes = dict(self.rec_b.prototypes)
        engine_no_margin = IntentEngine(config=self.config, action_mappings=action_mapping)
        engine_no_margin.reset(State.IDLE)

        # Dispatch collections
        dispatches_a: list[tuple[str, int]] = []
        dispatches_b: list[tuple[str, int]] = []
        dispatches_c: list[tuple[str, int]] = []
        dispatches_no_hold: list[tuple[str, int]] = []
        dispatches_no_rel: list[tuple[str, int]] = []
        dispatches_no_margin: list[tuple[str, int]] = []

        # Synchronous, bit-exact single pass across identical feature packets
        for pkt in feature_stream:
            # 1. Condition A: Fixed thresholds with conventional debounce
            res_a = self.rec_a.predict(pkt)
            disp_a = debouncer_a.step(res_a.accepted_candidate_or_none, pkt.t_ns)
            if disp_a is not None:
                dispatches_a.append(disp_a)

            # 2. Condition B: Personalized prototype with fair conventional debounce
            res_b = self.rec_b.predict(pkt)
            disp_b = debouncer_b.step(res_b.accepted_candidate_or_none, pkt.t_ns)
            if disp_b is not None:
                dispatches_b.append(disp_b)

            # 3. Condition C: Full MORPH System (Identical predictions through IntentEngine)
            _, cmd_c, _ = engine_c.step(
                recognition=res_b,
                tracking_valid=pkt.valid,
                now_ns=pkt.t_ns,
                mode="LIVE",
                paused=False,
            )
            if cmd_c is not None:
                dispatches_c.append((cmd_c.action_mapping_uuid, cmd_c.confirmed_at_ns))

            # Ablation 1: No Hold
            _, cmd_nh, _ = engine_no_hold.step(
                recognition=res_b,
                tracking_valid=pkt.valid,
                now_ns=pkt.t_ns,
                mode="LIVE",
                paused=False,
            )
            if cmd_nh is not None:
                dispatches_no_hold.append((cmd_nh.action_mapping_uuid, cmd_nh.confirmed_at_ns))

            # Ablation 2: No Release
            _, cmd_nr, _ = engine_no_rel.step(
                recognition=res_b,
                tracking_valid=pkt.valid,
                now_ns=pkt.t_ns,
                mode="LIVE",
                paused=False,
            )
            if cmd_nr is not None:
                dispatches_no_rel.append((cmd_nr.action_mapping_uuid, cmd_nr.confirmed_at_ns))

            # Ablation 3: No Margin
            res_b_nm = rec_b_no_margin.predict(pkt)
            _, cmd_nm, _ = engine_no_margin.step(
                recognition=res_b_nm,
                tracking_valid=pkt.valid,
                now_ns=pkt.t_ns,
                mode="LIVE",
                paused=False,
            )
            if cmd_nm is not None:
                dispatches_no_margin.append((cmd_nm.action_mapping_uuid, cmd_nm.confirmed_at_ns))

        def _evaluate(dispatches: list[tuple[str, int]]) -> dict[str, Any]:
            matched, unmatched_disp, unmatched_gt = match_events_one_to_one(
                ground_truth_events, dispatches, label_mapping=action_mapping
            )
            return calculate_benchmark_metrics(
                matched,
                unmatched_disp,
                unmatched_gt,
                session_duration_sec,
                total_intended_duration_sec,
            )

        metrics_a = _evaluate(dispatches_a)
        metrics_b = _evaluate(dispatches_b)
        metrics_c = _evaluate(dispatches_c)
        metrics_no_hold = _evaluate(dispatches_no_hold)
        metrics_no_rel = _evaluate(dispatches_no_rel)
        metrics_no_margin = _evaluate(dispatches_no_margin)

        return {
            "condition_a": metrics_a,
            "condition_b": metrics_b,
            "condition_c": metrics_c,
            "ablations": {
                "no_hold": metrics_no_hold,
                "no_release": metrics_no_rel,
                "no_margin": metrics_no_margin,
            },
            "metadata": {
                "is_synthetic": is_synthetic,
                "dataset_version": dataset_version,
                "total_frames": len(feature_stream),
                "total_intended_events": len(ground_truth_events),
                "session_duration_sec": session_duration_sec,
                "non_command_hours": metrics_c["non_command_hours"],
            },
        }
