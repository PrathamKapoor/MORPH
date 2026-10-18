"""Expanded 20-Scenario Synthetic Benchmark Challenge Suite for MORPH 2.0 (Milestone M6.2).

Provides 20 distinct challenge conditions covering natural resting movements,
involuntary twitches, deliberate sustained commands, ambiguity blends, head motion,
sensor occlusions, camera drift, timing anomalies, and extended non-command exposure.

All landmark and feature streams are explicitly labeled SYNTHETIC_FIXTURE.
Not human clinical or biometric data.
"""

from typing import Any

import numpy as np

from morph.common.types import (
    EvaluationScenario,
    FeaturePacket,
    GroundTruthEvent,
    LandmarkPacket,
)
from morph.evaluation.independence import DatasetIndependenceAuditor
from morph.features.normalizer import FeatureExtractor
from tests.fixtures.synthetic_faces import (
    create_synthetic_held_out_landmarks,
    create_synthetic_neutral_landmarks,
    create_synthetic_noise_landmarks,
)


def verify_zero_leakage(
    calibration_prototypes: dict[str, list[np.ndarray]],
    evaluation_stream: list[FeaturePacket],
    tolerance: float = 1e-4,
    calibration_seeds: list[int] | None = None,
    evaluation_seeds: list[int] | None = None,
    calibration_session_id: str | None = None,
    evaluation_session_id: str | None = None,
) -> dict[str, Any]:
    """Verify that no benchmark evaluation feature vector is identical to any calibration prototype vector.

    Audits pairwise Euclidean distances, generation seed isolation, and session boundaries.
    """
    auditor = DatasetIndependenceAuditor(tolerance=tolerance)
    audit_res = auditor.audit(
        calibration_prototypes=calibration_prototypes,
        evaluation_stream=evaluation_stream,
        calibration_seeds=calibration_seeds,
        evaluation_seeds=evaluation_seeds,
        calibration_session_id=calibration_session_id,
        evaluation_session_id=evaluation_session_id,
    )

    eval_vecs_count = sum(
        1
        for pkt in evaluation_stream
        if pkt.valid and pkt.vector is not None and len(pkt.vector) > 0
    )
    cal_vecs_count = sum(
        len([v for v in vecs if v is not None and len(v) > 0])
        for vecs in calibration_prototypes.values()
    )

    return {
        "zero_leakage_passed": audit_res.is_independent,
        "min_euclidean_distance": audit_res.min_euclidean_distance,
        "mean_euclidean_distance": audit_res.mean_euclidean_distance,
        "evaluated_frames": eval_vecs_count,
        "calibration_prototypes": cal_vecs_count,
        "tolerance": tolerance,
        "independence_audit": audit_res.to_dict(),
    }


class BenchmarkScenarioSuite:
    """Generates 20 distinct synthetic challenge scenarios for rigorous A/B/C evaluation."""

    def __init__(self, neutral_scale: float = 0.30):
        self.neutral_lm = create_synthetic_neutral_landmarks()
        self.neutral_scale = neutral_scale
        self.extractor = FeatureExtractor(self.neutral_lm, self.neutral_scale)

    def get_calibration_seeds(self) -> list[int]:
        """Return pseudo-random seeds used for calibration prototype generation."""
        return (
            [100 + rep for rep in range(5)]
            + [200 + rep for rep in range(5)]
            + [300 + rep for rep in range(5)]
        )

    def get_evaluation_seeds(self) -> list[int]:
        """Return pseudo-random seeds used for evaluation stream generation."""
        return [501, 502, 503, 504, 505, 506, 601, 602, 603, 701, 702, 801, 802, 803, 901]

    def get_calibration_prototypes(self) -> dict[str, list[np.ndarray]]:
        """Generate isolated calibration prototypes from simulated enrollment trials.

        Calibration prototypes use canonical reference poses with enrollment-session variations.
        Held-out evaluation frames are generated separately with distinct perturbations,
        guaranteeing zero data leakage.
        """
        cal_data: dict[str, list[np.ndarray]] = {
            "Brow Raise": [],
            "Smile / Lip Corner Pull": [],
            "Chin Raise / Mouth Open": [],
        }

        for rep in range(5):
            # Enrollment Brow Raise (seeds 100-104, canonical scale)
            brow_lm = create_synthetic_held_out_landmarks(
                "brow_raise",
                scale_offset=0.0,
                yaw_offset=0.0,
                pitch_offset=0.0,
                intensity=1.0 + 0.01 * (rep - 2),
                seed=100 + rep,
            )
            pkt_b = LandmarkPacket(
                frame_id=1000 + rep,
                t_ns=1_000_000_000 + rep * 100_000_000,
                face_count=1,
                normalized_landmarks=brow_lm,
                valid=True,
            )
            cal_data["Brow Raise"].append(self.extractor.extract(pkt_b).vector)

            # Enrollment Smile (seeds 200-204)
            smile_lm = create_synthetic_held_out_landmarks(
                "smile",
                scale_offset=0.0,
                yaw_offset=0.0,
                pitch_offset=0.0,
                intensity=1.0 + 0.01 * (rep - 2),
                seed=200 + rep,
            )
            pkt_s = LandmarkPacket(
                frame_id=2000 + rep,
                t_ns=2_000_000_000 + rep * 100_000_000,
                face_count=1,
                normalized_landmarks=smile_lm,
                valid=True,
            )
            cal_data["Smile / Lip Corner Pull"].append(self.extractor.extract(pkt_s).vector)

            # Enrollment Mouth Open (seeds 300-304)
            open_lm = create_synthetic_held_out_landmarks(
                "mouth_open",
                scale_offset=0.0,
                yaw_offset=0.0,
                pitch_offset=0.0,
                intensity=1.0 + 0.01 * (rep - 2),
                seed=300 + rep,
            )
            pkt_o = LandmarkPacket(
                frame_id=3000 + rep,
                t_ns=3_000_000_000 + rep * 100_000_000,
                face_count=1,
                normalized_landmarks=open_lm,
                valid=True,
            )
            cal_data["Chin Raise / Mouth Open"].append(self.extractor.extract(pkt_o).vector)

        return cal_data

    def _frame_time_ns(self, start_ns: int, frame_idx: int, fps: float = 30.0) -> int:
        interval_ns = int(1e9 / fps)
        return start_ns + frame_idx * interval_ns

    def build_scenario_stream(
        self,
        scenario: EvaluationScenario | str,
        start_time_ns: int = 1_000_000_000,
    ) -> tuple[list[FeaturePacket], list[GroundTruthEvent], float]:
        """Generate a focused evaluation stream for one of the 8 research evaluation scenarios.

        Returns:
            stream: Chronologically ordered list of FeaturePackets.
            ground_truth: GroundTruthEvents corresponding to deliberate gestures.
            duration_sec: Total scenario stream duration in seconds.
        """
        stream: list[FeaturePacket] = []
        ground_truth: list[GroundTruthEvent] = []
        t_cur = start_time_ns
        frame_id = 0

        def append_lm(
            lm: np.ndarray,
            t: int,
            valid: bool = True,
            face_count: int = 1,
            blendshapes: dict[str, float] | None = None,
        ):
            nonlocal frame_id
            frame_id += 1
            pkt = LandmarkPacket(
                frame_id=frame_id,
                t_ns=t,
                face_count=face_count,
                normalized_landmarks=lm,
                blendshapes=blendshapes or {},
                valid=valid,
                failure_reason="" if valid else "SYNTHETIC_CHALLENGE_INVALID",
            )
            stream.append(self.extractor.extract(pkt))

        s_val = scenario.value if isinstance(scenario, EvaluationScenario) else str(scenario)

        if s_val == EvaluationScenario.SCEN_01_INTENDED.value or "INTENDED" in s_val:
            # 3 deliberate commands: Brow Raise, Smile, Mouth Open (each 400ms hold, 250ms threshold)
            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

            # Brow Raise
            s_brow = t_cur
            brow_lm = create_synthetic_held_out_landmarks("brow_raise", intensity=0.96, seed=501)
            for f in range(12):
                append_lm(brow_lm, self._frame_time_ns(t_cur, f))
            e_brow = self._frame_time_ns(t_cur, 12)
            ground_truth.append(
                GroundTruthEvent("Brow Raise", s_brow, e_brow, "benchmark", "scen_01")
            )
            t_cur = self._frame_time_ns(t_cur, 12)

            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

            # Smile
            s_smile = t_cur
            smile_lm = create_synthetic_held_out_landmarks("smile", intensity=0.96, seed=601)
            for f in range(12):
                append_lm(smile_lm, self._frame_time_ns(t_cur, f))
            e_smile = self._frame_time_ns(t_cur, 12)
            ground_truth.append(
                GroundTruthEvent(
                    "Smile / Lip Corner Pull", s_smile, e_smile, "benchmark", "scen_01"
                )
            )
            t_cur = self._frame_time_ns(t_cur, 12)

            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

            # Mouth Open
            s_mouth = t_cur
            open_lm = create_synthetic_held_out_landmarks("mouth_open", intensity=0.96, seed=701)
            for f in range(12):
                append_lm(open_lm, self._frame_time_ns(t_cur, f))
            e_mouth = self._frame_time_ns(t_cur, 12)
            ground_truth.append(
                GroundTruthEvent(
                    "Chin Raise / Mouth Open", s_mouth, e_mouth, "benchmark", "scen_01"
                )
            )
            t_cur = self._frame_time_ns(t_cur, 12)

            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

        elif s_val == EvaluationScenario.SCEN_02_NEUTRAL.value or "NEUTRAL" in s_val:
            # 600 frames resting baseline + rhythmic blinks, 0 GT
            for f in range(600):
                cur_lm = self.neutral_lm.copy()
                is_blink = (100 <= f <= 103) or (300 <= f <= 303) or (500 <= f <= 503)
                if is_blink:
                    cur_lm[105, 1] += 0.005
                append_lm(
                    cur_lm,
                    self._frame_time_ns(t_cur, f),
                    blendshapes={"eyeBlinkLeft": 0.85, "eyeBlinkRight": 0.85} if is_blink else {},
                )
            t_cur = self._frame_time_ns(t_cur, 600)

        elif s_val == EvaluationScenario.SCEN_03_DISTRACTOR.value or "DISTRACTOR" in s_val:
            # 60ms brow twitch, 120ms lip twitch, yaw/pitch turns, 0 GT
            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

            # 60ms twitch
            b_tw = create_synthetic_held_out_landmarks("brow_raise", intensity=0.90, seed=801)
            for f in range(2):
                append_lm(b_tw, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 2)

            for f in range(25):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 25)

            # 120ms twitch
            s_tw = create_synthetic_held_out_landmarks("smile", intensity=0.90, seed=802)
            for f in range(4):
                append_lm(s_tw, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 4)

            for f in range(25):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 25)

            # Head yaw turn
            for f in range(25):
                yaw_lm = self.neutral_lm.copy()
                yaw_lm[:, 0] += 0.015 * np.sin(f / 25.0 * np.pi)
                append_lm(yaw_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 25)

            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

        elif s_val == EvaluationScenario.SCEN_04_BOARD_TASK.value or "BOARD" in s_val:
            # AAC Board sequence: Next -> Next -> Select
            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

            # Next 1 (Brow Raise)
            s_b1 = t_cur
            b_lm = create_synthetic_held_out_landmarks("brow_raise", intensity=0.96, seed=502)
            for f in range(12):
                append_lm(b_lm, self._frame_time_ns(t_cur, f))
            e_b1 = self._frame_time_ns(t_cur, 12)
            ground_truth.append(GroundTruthEvent("Brow Raise", s_b1, e_b1, "benchmark", "scen_04"))
            t_cur = self._frame_time_ns(t_cur, 12)

            for f in range(25):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 25)

            # Next 2 (Brow Raise)
            s_b2 = t_cur
            b_lm2 = create_synthetic_held_out_landmarks("brow_raise", intensity=0.96, seed=503)
            for f in range(12):
                append_lm(b_lm2, self._frame_time_ns(t_cur, f))
            e_b2 = self._frame_time_ns(t_cur, 12)
            ground_truth.append(GroundTruthEvent("Brow Raise", s_b2, e_b2, "benchmark", "scen_04"))
            t_cur = self._frame_time_ns(t_cur, 12)

            for f in range(25):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 25)

            # Select (Smile)
            s_s1 = t_cur
            sm_lm = create_synthetic_held_out_landmarks("smile", intensity=0.96, seed=602)
            for f in range(12):
                append_lm(sm_lm, self._frame_time_ns(t_cur, f))
            e_s1 = self._frame_time_ns(t_cur, 12)
            ground_truth.append(
                GroundTruthEvent("Smile / Lip Corner Pull", s_s1, e_s1, "benchmark", "scen_04")
            )
            t_cur = self._frame_time_ns(t_cur, 12)

            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

        elif s_val == EvaluationScenario.SCEN_05_PAUSE_RECOVERY.value or "PAUSE" in s_val:
            # Tracking loss -> recovery -> Brow Raise
            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

            # 20 frames tracking loss
            for f in range(20):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f), valid=False, face_count=0)
            t_cur = self._frame_time_ns(t_cur, 20)

            # 30 frames recovery
            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

            # Command after recovery
            s_c = t_cur
            b_lm = create_synthetic_held_out_landmarks("brow_raise", intensity=0.96, seed=504)
            for f in range(12):
                append_lm(b_lm, self._frame_time_ns(t_cur, f))
            e_c = self._frame_time_ns(t_cur, 12)
            ground_truth.append(GroundTruthEvent("Brow Raise", s_c, e_c, "benchmark", "scen_05"))
            t_cur = self._frame_time_ns(t_cur, 12)

            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

        elif s_val == EvaluationScenario.SCEN_06_CAMERA_DRIFT.value or "DRIFT" in s_val:
            # Scale reduction and drift + command
            shrunk_lm = self.neutral_lm.copy()
            center = shrunk_lm[1].copy()
            shrunk_lm = center + (shrunk_lm - center) * 0.70  # 30% scale reduction
            for f in range(30):
                append_lm(shrunk_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

            s_cd = t_cur
            b_shrunk = create_synthetic_held_out_landmarks("brow_raise", intensity=0.96, seed=505)
            b_shrunk = center + (b_shrunk - center) * 0.70
            for f in range(12):
                append_lm(b_shrunk, self._frame_time_ns(t_cur, f))
            e_cd = self._frame_time_ns(t_cur, 12)
            ground_truth.append(GroundTruthEvent("Brow Raise", s_cd, e_cd, "benchmark", "scen_06"))
            t_cur = self._frame_time_ns(t_cur, 12)

            for f in range(30):
                append_lm(shrunk_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

        elif s_val == EvaluationScenario.SCEN_07_CROSS_SESSION.value or "CROSS" in s_val:
            # Independent session stream
            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

            s_cs1 = t_cur
            sm_lm = create_synthetic_held_out_landmarks("smile", intensity=0.96, seed=603)
            for f in range(12):
                append_lm(sm_lm, self._frame_time_ns(t_cur, f))
            e_cs1 = self._frame_time_ns(t_cur, 12)
            ground_truth.append(
                GroundTruthEvent("Smile / Lip Corner Pull", s_cs1, e_cs1, "benchmark", "scen_07")
            )
            t_cur = self._frame_time_ns(t_cur, 12)

            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

            s_cs2 = t_cur
            mo_lm = create_synthetic_held_out_landmarks("mouth_open", intensity=0.96, seed=702)
            for f in range(12):
                append_lm(mo_lm, self._frame_time_ns(t_cur, f))
            e_cs2 = self._frame_time_ns(t_cur, 12)
            ground_truth.append(
                GroundTruthEvent("Chin Raise / Mouth Open", s_cs2, e_cs2, "benchmark", "scen_07")
            )
            t_cur = self._frame_time_ns(t_cur, 12)

            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

        else:
            # Default / SCEN_08_RECALIBRATION: Command + twitch + neutral
            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

            s_rc = t_cur
            b_lm = create_synthetic_held_out_landmarks("brow_raise", intensity=0.96, seed=506)
            for f in range(12):
                append_lm(b_lm, self._frame_time_ns(t_cur, f))
            e_rc = self._frame_time_ns(t_cur, 12)
            ground_truth.append(GroundTruthEvent("Brow Raise", s_rc, e_rc, "benchmark", "scen_08"))
            t_cur = self._frame_time_ns(t_cur, 12)

            for f in range(25):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 25)

            # Distractor twitch
            b_tw = create_synthetic_held_out_landmarks("brow_raise", intensity=0.90, seed=803)
            for f in range(2):
                append_lm(b_tw, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 2)

            for f in range(30):
                append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
            t_cur = self._frame_time_ns(t_cur, 30)

        duration_sec = (t_cur - start_time_ns) / 1_000_000_000.0
        return stream, ground_truth, duration_sec

    def build_full_challenge_stream(
        self, start_time_ns: int = 1_000_000_000
    ) -> tuple[list[FeaturePacket], list[GroundTruthEvent], dict[str, tuple[int, int]]]:
        """Build a continuous, timestamped sequence concatenating all 20 challenge scenarios.

        Returns:
            stream: Chronologically ordered list of FeaturePackets.
            ground_truth: GroundTruthEvents corresponding to deliberate gestures.
            scenario_intervals: Mapping of scenario name to (start_ns, end_ns).
        """
        stream: list[FeaturePacket] = []
        ground_truth: list[GroundTruthEvent] = []
        scenario_intervals: dict[str, tuple[int, int]] = {}

        t_cur = start_time_ns
        frame_id = 0

        # Helper to append landmark packet
        def append_lm(
            lm: np.ndarray,
            t: int,
            valid: bool = True,
            face_count: int = 1,
            blendshapes: dict[str, float] | None = None,
        ):
            nonlocal frame_id
            frame_id += 1
            pkt = LandmarkPacket(
                frame_id=frame_id,
                t_ns=t,
                face_count=face_count,
                normalized_landmarks=lm,
                blendshapes=blendshapes or {},
                valid=valid,
                failure_reason="" if valid else "SYNTHETIC_CHALLENGE_INVALID",
            )
            feat = self.extractor.extract(pkt)
            stream.append(feat)

        # Scenario 1: NATURAL_REST_NEUTRAL (60 frames resting, 2.0s)
        s1_start = t_cur
        for f in range(60):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 60)
        scenario_intervals["01_natural_rest_neutral"] = (s1_start, t_cur)

        # Scenario 2: NATURAL_BLINKS (30 frames with 2 distinct blinks)
        s2_start = t_cur
        blink_lm = self.neutral_lm.copy()
        for f in range(30):
            # Blink at frame 10-12 and frame 22-24
            cur_lm = blink_lm.copy()
            if 10 <= f <= 12 or 22 <= f <= 24:
                # Eyelids close: outer corners stay, upper eyelid lowers
                cur_lm[105, 1] += 0.005  # slight brow relaxation
            append_lm(
                cur_lm,
                self._frame_time_ns(t_cur, f),
                blendshapes={"eyeBlinkLeft": 0.85, "eyeBlinkRight": 0.85}
                if (10 <= f <= 12 or 22 <= f <= 24)
                else {},
            )
        t_cur = self._frame_time_ns(t_cur, 30)
        scenario_intervals["02_natural_blinks"] = (s2_start, t_cur)

        # Scenario 3: MICRO_TWITCH_60MS (2 frames brow twitch, 60ms < hold_ms)
        s3_start = t_cur
        brow_twitch_lm = create_synthetic_held_out_landmarks(
            "brow_raise",
            scale_offset=-0.015,
            yaw_offset=0.003,
            pitch_offset=-0.002,
            intensity=0.90,
            seed=801,
        )
        for f in range(2):
            append_lm(brow_twitch_lm, self._frame_time_ns(t_cur, f))
        for f in range(2, 20):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 20)
        scenario_intervals["03_micro_twitch_60ms"] = (s3_start, t_cur)

        # Scenario 4: MICRO_TWITCH_120MS (4 frames smile twitch, 120ms < hold_ms)
        s4_start = t_cur
        smile_twitch_lm = create_synthetic_held_out_landmarks(
            "smile",
            scale_offset=-0.015,
            yaw_offset=0.003,
            pitch_offset=-0.002,
            intensity=0.90,
            seed=802,
        )
        for f in range(4):
            append_lm(smile_twitch_lm, self._frame_time_ns(t_cur, f))
        for f in range(4, 20):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 20)
        scenario_intervals["04_micro_twitch_120ms"] = (s4_start, t_cur)

        # Scenario 5: SUSTAINED_BROW_RAISE (Deliberate command, 12 frames = 400ms >= 250ms hold)
        s5_start = t_cur
        brow_hold_lm = create_synthetic_held_out_landmarks(
            "brow_raise",
            scale_offset=-0.015,
            yaw_offset=0.003,
            pitch_offset=-0.002,
            intensity=0.96,
            seed=501,
        )
        for f in range(12):
            append_lm(brow_hold_lm, self._frame_time_ns(t_cur, f))
        s5_end = self._frame_time_ns(t_cur, 12)
        ground_truth.append(
            GroundTruthEvent(
                label="Brow Raise",
                start_ns=s5_start,
                end_ns=s5_end,
                annotator="synthetic_benchmark",
                session_id="benchmark_suite_v2",
            )
        )
        # Release back to neutral for 20 frames
        for f in range(12, 32):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 32)
        scenario_intervals["05_sustained_brow_raise"] = (s5_start, t_cur)

        # Scenario 6: SUSTAINED_SMILE (Deliberate command, 12 frames = 400ms)
        s6_start = t_cur
        smile_hold_lm = create_synthetic_held_out_landmarks(
            "smile",
            scale_offset=-0.015,
            yaw_offset=0.003,
            pitch_offset=-0.002,
            intensity=0.97,
            seed=601,
        )
        for f in range(12):
            append_lm(smile_hold_lm, self._frame_time_ns(t_cur, f))
        s6_end = self._frame_time_ns(t_cur, 12)
        ground_truth.append(
            GroundTruthEvent(
                label="Smile / Lip Corner Pull",
                start_ns=s6_start,
                end_ns=s6_end,
                annotator="synthetic_benchmark",
                session_id="benchmark_suite_v2",
            )
        )
        for f in range(12, 32):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 32)
        scenario_intervals["06_sustained_smile"] = (s6_start, t_cur)

        # Scenario 7: SUSTAINED_MOUTH_OPEN (Deliberate command, 12 frames = 400ms)
        s7_start = t_cur
        open_hold_lm = create_synthetic_held_out_landmarks(
            "mouth_open",
            scale_offset=-0.015,
            yaw_offset=0.003,
            pitch_offset=-0.002,
            intensity=0.96,
            seed=701,
        )
        for f in range(12):
            append_lm(open_hold_lm, self._frame_time_ns(t_cur, f))
        s7_end = self._frame_time_ns(t_cur, 12)
        ground_truth.append(
            GroundTruthEvent(
                label="Chin Raise / Mouth Open",
                start_ns=s7_start,
                end_ns=s7_end,
                annotator="synthetic_benchmark",
                session_id="benchmark_suite_v2",
            )
        )
        for f in range(12, 32):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 32)
        scenario_intervals["07_sustained_mouth_open"] = (s7_start, t_cur)

        # Scenario 8: AMBIGUOUS_BLEND_BROW_SMILE (Simultaneous brow + smile, 12 frames)
        s8_start = t_cur
        blend_lm = (brow_hold_lm + smile_hold_lm) / 2.0
        for f in range(12):
            append_lm(blend_lm, self._frame_time_ns(t_cur, f))
        for f in range(12, 32):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 32)
        scenario_intervals["08_ambiguous_blend_brow_smile"] = (s8_start, t_cur)

        # Scenario 9: RAPID_REPETITION_PULSE (Two brow raises separated by only 3 frames = 100ms < cooldown)
        s9_start = t_cur
        brow_rep_lm = create_synthetic_held_out_landmarks(
            "brow_raise",
            scale_offset=-0.015,
            yaw_offset=0.003,
            pitch_offset=-0.002,
            intensity=0.95,
            seed=901,
        )
        for f in range(12):
            append_lm(brow_rep_lm, self._frame_time_ns(t_cur, f))
        ground_truth.append(
            GroundTruthEvent(
                label="Brow Raise",
                start_ns=s9_start,
                end_ns=self._frame_time_ns(t_cur, 12),
                annotator="synthetic_benchmark",
                session_id="benchmark_suite_v2",
            )
        )
        # Brief 3-frame neutral dip (100ms)
        for f in range(12, 15):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
        # Immediate second brow raise during cooldown window
        for f in range(15, 27):
            append_lm(brow_rep_lm, self._frame_time_ns(t_cur, f))
        # 25 frames rest
        for f in range(27, 52):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 52)
        scenario_intervals["09_rapid_repetition_pulse"] = (s9_start, t_cur)

        # Scenario 10: HEAD_YAW_TURN (Nose moves sideways by 0.08, 25 frames)
        s10_start = t_cur
        yaw_lm = self.neutral_lm.copy()
        yaw_lm[:, 0] += 0.08
        for f in range(25):
            append_lm(yaw_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 25)
        scenario_intervals["10_head_yaw_turn"] = (s10_start, t_cur)

        # Scenario 11: HEAD_PITCH_NOD (Head pitches downwards, 25 frames)
        s11_start = t_cur
        pitch_lm = self.neutral_lm.copy()
        pitch_lm[:, 1] += 0.06
        for f in range(25):
            append_lm(pitch_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 25)
        scenario_intervals["11_head_pitch_nod"] = (s11_start, t_cur)

        # Scenario 12: HEAD_ROLL_TILT (Rotational tilt, 25 frames)
        s12_start = t_cur
        roll_lm = self.neutral_lm.copy()
        roll_lm[:, 0] += 0.03
        roll_lm[:, 1] -= 0.03
        for f in range(25):
            append_lm(roll_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 25)
        scenario_intervals["12_head_roll_tilt"] = (s12_start, t_cur)

        # Scenario 13: MULTI_FACE_OCCLUSION (face_count = 2, invalid, 15 frames)
        s13_start = t_cur
        for f in range(15):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f), valid=False, face_count=2)
        for f in range(15, 30):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f), valid=True, face_count=1)
        t_cur = self._frame_time_ns(t_cur, 30)
        scenario_intervals["13_multi_face_occlusion"] = (s13_start, t_cur)

        # Scenario 14: LIGHTING_INTENSITY_DRIFT (Random coordinate perturbation, 20 frames)
        s14_start = t_cur
        drift_lm = create_synthetic_noise_landmarks()
        for f in range(20):
            append_lm(drift_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 20)
        scenario_intervals["14_lighting_intensity_drift"] = (s14_start, t_cur)

        # Scenario 15: DROPPED_FRAME_BURST (Gap of 650ms > 500ms max_gap, candidate abort)
        s15_start = t_cur
        brow_drop_lm = create_synthetic_held_out_landmarks(
            "brow_raise",
            scale_offset=-0.015,
            yaw_offset=0.003,
            pitch_offset=-0.002,
            intensity=0.94,
            seed=951,
        )
        # 3 frames of candidate
        for f in range(3):
            append_lm(brow_drop_lm, self._frame_time_ns(t_cur, f))
        # 650ms jump to next frame
        t_jump = self._frame_time_ns(t_cur, 3) + 650_000_000
        append_lm(brow_drop_lm, t_jump)
        # return to neutral
        for f in range(1, 15):
            append_lm(self.neutral_lm, self._frame_time_ns(t_jump, f))
        t_cur = self._frame_time_ns(t_jump, 15)
        scenario_intervals["15_dropped_frame_burst"] = (s15_start, t_cur)

        # Scenario 16: STALE_DUPLICATE_FRAME (Identical timestamps across 3 frames)
        s16_start = t_cur
        t_stale = self._frame_time_ns(t_cur, 1)
        append_lm(self.neutral_lm, t_stale)
        append_lm(self.neutral_lm, t_stale)
        append_lm(self.neutral_lm, t_stale)
        for f in range(2, 15):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 15)
        scenario_intervals["16_stale_duplicate_frame"] = (s16_start, t_cur)

        # Scenario 17: CLOCK_JITTER_REVERSAL (Monotonic regression, 1 frame jumps backward 20ms)
        s17_start = t_cur
        t_prev = self._frame_time_ns(t_cur, 5)
        append_lm(self.neutral_lm, t_prev)
        append_lm(self.neutral_lm, t_prev - 20_000_000)  # Clock regression
        for f in range(6, 15):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 15)
        scenario_intervals["17_clock_jitter_reversal"] = (s17_start, t_cur)

        # Scenario 18: NAN_INF_FEATURE_CORRUPTION (Non-finite packet, 5 frames)
        s18_start = t_cur
        corrupt_lm = self.neutral_lm.copy()
        corrupt_lm[105, 0] = float("nan")
        for f in range(5):
            append_lm(corrupt_lm, self._frame_time_ns(t_cur, f))
        for f in range(5, 15):
            append_lm(self.neutral_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 15)
        scenario_intervals["18_nan_inf_feature_corruption"] = (s18_start, t_cur)

        # Scenario 19: INTEROCULAR_SCALE_REDUCTION (Face moves further back: 50% scale)
        s19_start = t_cur
        shrunk_lm = self.neutral_lm.copy()
        center = shrunk_lm[1].copy()
        shrunk_lm = center + (shrunk_lm - center) * 0.50
        for f in range(25):
            append_lm(shrunk_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 25)
        scenario_intervals["19_interocular_scale_reduction"] = (s19_start, t_cur)

        # Scenario 20: LONG_NON_COMMAND_EXPOSURE (3,000 frames = 100 seconds conversational non-command)
        s20_start = t_cur
        for f in range(3000):
            # Subtle rhythmic conversational movement
            cur_lm = self.neutral_lm.copy()
            cur_lm[14, 1] += 0.005 * np.sin(f * 0.1)  # tiny mouth movement
            append_lm(cur_lm, self._frame_time_ns(t_cur, f))
        t_cur = self._frame_time_ns(t_cur, 3000)
        scenario_intervals["20_long_non_command_exposure"] = (s20_start, t_cur)

        return stream, ground_truth, scenario_intervals
