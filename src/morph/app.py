"""Application coordinator connecting capture worker, recognition, intent FSM, and TTS."""

from __future__ import annotations

import sys
import time

import numpy as np
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from morph.actions.dispatcher import ActionDispatcher
from morph.actions.tts import WindowsSapiTTS
from morph.capture.camera import OpenCVCameraAdapter
from morph.capture.instrumentation import PerformanceMonitor
from morph.capture.tracker import MediaPipeFaceTracker
from morph.capture.worker import CaptureWorker
from morph.common.config import RecognitionConfig
from morph.common.types import LandmarkPacket, State, TrackingHealth
from morph.features.normalizer import FeatureExtractor
from morph.intent.engine import IntentEngine
from morph.recognition.recognizer_a import BaselineRecognizerA
from morph.recognition.recognizer_b import PersonalizedRecognizerB
from morph.storage.profiles import ProfileStore
from morph.ui.main_window import MainWindow


class MorphApplication(QObject):
    """Coordinates camera worker, feature extraction, recognition, intent gating FSM,

    action dispatch, and PySide6 user interface.
    """

    def __init__(self, sys_argv: list[str] | None = None):
        super().__init__()
        self.app = QApplication.instance() or QApplication(sys_argv or sys.argv)
        self.app.setApplicationName("MORPH 2.0")
        self.app.setOrganizationName("PrathamKapoor")

        self.config = RecognitionConfig()
        self.store = ProfileStore()
        self.active_profile_uuid = self.store.get_or_create_default_profile()

        # Pure core components
        self.normalizer = FeatureExtractor()
        self.recognizer = PersonalizedRecognizerB(
            min_similarity=self.config.min_similarity,
            min_margin=self.config.min_margin,
            profile_version=self.active_profile_uuid,
        )
        self.intent_engine = IntentEngine(config=self.config)
        self.dispatcher = ActionDispatcher(mode="LIVE")
        self.perf_monitor = PerformanceMonitor()

        # Offline TTS
        try:
            self.tts = WindowsSapiTTS()
        except Exception:
            self.tts = None

        self.window = MainWindow()

        # Load stored profile calibration if present
        self._load_active_profile()

        # Initialize hardware capture worker safely
        self._init_worker()

        # Wire all Qt signals
        self._wire_signals()

    def _load_active_profile(self) -> None:
        """Load stored neutral baseline and model snapshot from SQLite."""
        baseline = self.store.get_neutral_baseline(self.active_profile_uuid)
        if baseline:
            lm, scale = baseline
            self.normalizer.set_neutral_baseline(lm, scale)
            self.window.studio_view.lbl_neutral_status.setText(
                "Neutral Baseline: Calibrated and active from stored profile."
            )
        else:
            self.normalizer.clear_baseline()
            self.window.studio_view.lbl_neutral_status.setText(
                "Neutral Baseline: Not calibrated for this profile."
            )

        snapshot = self.store.get_latest_model_snapshot(self.active_profile_uuid)
        if snapshot and "weights" in snapshot:
            self.recognizer.from_dict(snapshot["weights"])
        else:
            self.recognizer.prototypes.clear()

        profiles = self.store.list_profiles()
        self.window.home_view.set_profiles(profiles, self.active_profile_uuid)

    def switch_profile(self, profile_uuid: str) -> None:
        """Atomically switch active profile with fail-closed pause and model swap."""
        if profile_uuid == self.active_profile_uuid:
            return

        # 1. Unconditional fail-closed pause
        self.window.force_pause()
        self.intent_engine.reset(State.PAUSED)

        # 2. Update active profile in store and state
        self.active_profile_uuid = profile_uuid
        self.store.set_active_profile(profile_uuid)

        # 3. Reload profile baseline & gesture prototypes
        self._load_active_profile()
        self.recognizer.profile_version = profile_uuid

        # 4. Guarantee engine remains safely paused until user explicitly activates
        self.intent_engine.reset(State.PAUSED)

    def _init_worker(self) -> None:
        """Initialize OpenCV camera and MediaPipe tracker inside background thread."""
        try:
            camera = OpenCVCameraAdapter(camera_index=self.config.camera_index)
            tracker = MediaPipeFaceTracker()
            self.worker = CaptureWorker(camera=camera, tracker=tracker, config=self.config)
        except Exception as e:
            print(f"[MORPH Startup Warning] Camera/tracker unavailable: {e}")
            self.worker = None

    def _wire_signals(self) -> None:
        # Pause/Resume controls
        self.window.pause_requested.connect(self._on_pause)
        self.window.resume_requested.connect(self._on_resume)

        # Profile switching
        self.window.profile_changed.connect(self.switch_profile)

        # Settings updates
        self.window.settings_view.settings_saved.connect(self._on_settings_saved)

        # Studio Practice Mode
        self.window.studio_view.practice_toggled.connect(self._on_practice_toggled)

        # Research Lab Replay and Export
        self.window.lab_view.run_abc_replay_requested.connect(self._on_run_abc_replay)
        self.window.lab_view.export_json_requested.connect(self._on_export_json)
        self.window.lab_view.export_csv_requested.connect(self._on_export_csv)

        # Register Dispatcher Handlers for allow-listed AAC actions
        self.dispatcher.register_handler("NEXT_TILE", self.window.board_view.navigate_next)
        self.dispatcher.register_handler("PREVIOUS_TILE", self.window.board_view.navigate_previous)
        self.dispatcher.register_handler("SELECT_TILE", self._handle_select_tile)
        self.dispatcher.register_handler("SPEAK_TILE", self._handle_select_tile)
        self.dispatcher.register_handler("PAUSE", self.window.force_pause)

        # Connect speech output from board
        self.window.board_view.phrase_spoken.connect(self._speak_phrase)

        # Worker signals
        if self.worker is not None:
            self.worker.landmark_ready.connect(self._on_landmark_packet)
            self.worker.health_updated.connect(self._on_worker_health)
            self.worker.error_occurred.connect(self._on_worker_error)
            self.worker.start()
        else:
            offline_health = TrackingHealth(
                processed_fps=0.0,
                capture_fps=0.0,
                dropped_frames=0,
                stale_frames=0,
                face_count=0,
                last_block_reason="NO_CAMERA_HARDWARE_OR_MODEL_MISSING",
                camera_connected=False,
            )
            self.window.update_health(offline_health)

    def _on_worker_health(self, health: TrackingHealth) -> None:
        """Handle worker telemetry updates and refresh performance monitor."""
        self.perf_monitor.update_queue_metrics(
            queue_depth=0,
            dropped=health.dropped_frames,
            stale=health.stale_frames,
            out_of_order=health.out_of_order_frames,
        )
        self.window.update_health(health)
        self.window.monitor_view.update_performance(self.perf_monitor.snapshot())

    def _on_landmark_packet(self, packet: LandmarkPacket) -> None:
        """Process incoming camera landmark packet through normalization, recognition, and intent gating."""
        now_ns = time.monotonic_ns()
        self.perf_monitor.record_capture_event(packet.captured_at_monotonic_ns)
        self.perf_monitor.record_process_event(now_ns)
        e2e_ms = (now_ns - packet.captured_at_monotonic_ns) / 1_000_000.0
        self.perf_monitor.record_stage_latency("end_to_end", e2e_ms)
        if packet.t_infer_end_ns > packet.t_infer_start_ns:
            self.perf_monitor.record_stage_latency(
                "landmark", (packet.t_infer_end_ns - packet.t_infer_start_ns) / 1_000_000.0
            )

        # 1. Feature Extraction & Neutral Normalization
        with self.perf_monitor.measure_stage("features"):
            feature_packet = self.normalizer.extract(packet)

        # 2. Personalized Recognition (Condition B)
        with self.perf_monitor.measure_stage("recognition"):
            recognition_result = self.recognizer.predict(feature_packet)

        # Update studio practice mode view if practice is active
        self.window.studio_view.update_practice_result(recognition_result)

        # 3. Deterministic Intention Gating State Machine (Condition C)
        paused = self.window._state == State.PAUSED
        with self.perf_monitor.measure_stage("intent"):
            state, command, transitions = self.intent_engine.step(
                recognition=recognition_result,
                tracking_valid=packet.valid,
                now_ns=now_ns,
                mode=self.dispatcher.mode,
                paused=paused,
            )

        # Forward transition events to monitor log
        for trans in transitions:
            self.window.monitor_view.append_transition(trans)

        # Update window state badge if tracking lost
        if state == State.TRACKING_LOST and self.window._state != State.TRACKING_LOST:
            self.window.set_system_state(State.TRACKING_LOST)
        elif state == State.IDLE and self.window._state == State.TRACKING_LOST:
            self.window.set_system_state(State.IDLE)

        # 4. Action Dispatch
        if command is not None:
            with self.perf_monitor.measure_stage("dispatch"):
                self.dispatcher.dispatch(command)

    def _handle_select_tile(self) -> None:
        """Select and speak the focused phrase tile."""
        self.window.board_view.select_current()

    def _speak_phrase(self, text: str) -> None:
        """Speak phrase via local offline TTS."""
        if self.tts:
            self.tts.speak(text)

    def _on_pause(self) -> None:
        self.window.set_system_state(State.PAUSED)
        self.intent_engine.reset(State.PAUSED)

    def _on_resume(self) -> None:
        self.window.set_system_state(State.IDLE)
        self.intent_engine.reset(State.IDLE)

    def _on_practice_toggled(self, in_practice: bool) -> None:
        self.dispatcher.mode = "PRACTICE" if in_practice else "LIVE"

    def _on_run_abc_replay(self) -> None:
        """Run reproducible A/B/C replay benchmark and update LabView table."""
        from morph.common.types import FeaturePacket, GroundTruthEvent
        from morph.evaluation.replay import ReplayEngine
        from tests.fixtures.synthetic_faces import (
            create_synthetic_brow_raise_landmarks,
            create_synthetic_mouth_open_landmarks,
            create_synthetic_neutral_landmarks,
            create_synthetic_smile_landmarks,
        )

        # Construct a controlled, reproducible stream
        # 1. Neutral baseline setup
        neutral_lm = create_synthetic_neutral_landmarks()
        eye_dist = 0.30
        extractor = FeatureExtractor(neutral_lm, eye_dist)

        # 2. Train Recognizer B
        brow_proto = extractor.extract(
            LandmarkPacket(
                frame_id=1,
                t_ns=1000,
                face_count=1,
                normalized_landmarks=create_synthetic_brow_raise_landmarks(),
                valid=True,
            )
        ).vector
        smile_proto = extractor.extract(
            LandmarkPacket(
                frame_id=2,
                t_ns=2000,
                face_count=1,
                normalized_landmarks=create_synthetic_smile_landmarks(),
                valid=True,
            )
        ).vector
        mouth_proto = extractor.extract(
            LandmarkPacket(
                frame_id=3,
                t_ns=3000,
                face_count=1,
                normalized_landmarks=create_synthetic_mouth_open_landmarks(),
                valid=True,
            )
        ).vector

        rec_b = PersonalizedRecognizerB(
            min_similarity=self.config.min_similarity, min_margin=self.config.min_margin
        )
        rec_b.fit(
            {
                "Brow Raise": [brow_proto] * 5,
                "Smile / Lip Corner Pull": [smile_proto] * 5,
                "Chin Raise / Mouth Open": [mouth_proto] * 5,
            }
        )

        rec_a = BaselineRecognizerA()
        replay = ReplayEngine(config=self.config, rec_a=rec_a, rec_b=rec_b)

        # 3. Build sequence of frames:
        # Deliberate gestures (5 total): Brow Raise x2, Smile x2, Mouth Open x1
        # Non-command challenges: involuntary 60ms twitch, 350ms ambiguous blend
        packets: list[FeaturePacket] = []
        frame_idx = 0
        now_base = 10_000_000_000  # 10s baseline

        def _append_frames(landmarks: np.ndarray, count: int) -> tuple[int, int]:
            nonlocal frame_idx
            start_t = now_base + (frame_idx + 1) * 33_333_333
            for _ in range(count):
                frame_idx += 1
                t = now_base + frame_idx * 33_333_333
                pkt = extractor.extract(
                    LandmarkPacket(
                        frame_id=frame_idx,
                        t_ns=t,
                        face_count=1,
                        normalized_landmarks=landmarks,
                        valid=True,
                    )
                )
                packets.append(pkt)
            return start_t, now_base + frame_idx * 33_333_333

        brow_lm = create_synthetic_brow_raise_landmarks()
        smile_lm = create_synthetic_smile_landmarks()
        mouth_lm = create_synthetic_mouth_open_landmarks()
        # Ambiguous blend: brow + smile combined
        blend_lm = brow_lm.copy()
        blend_lm[:, 0] = smile_lm[:, 0]

        # 1. Initial Neutral (90 frames ~ 3.0s)
        _append_frames(neutral_lm, 90)

        # 2. Intentional Brow Raise 1 (11 frames ~ 360ms)
        br1_start, br1_end = _append_frames(brow_lm, 11)

        # 3. Neutral rest (45 frames ~ 1.5s)
        _append_frames(neutral_lm, 45)

        # 4. Involuntary Brow Twitch (2 frames ~ 66ms, non-command challenge)
        _append_frames(brow_lm, 2)

        # 5. Neutral rest (45 frames ~ 1.5s)
        _append_frames(neutral_lm, 45)

        # 6. Intentional Smile 1 (11 frames ~ 360ms)
        sm1_start, sm1_end = _append_frames(smile_lm, 11)

        # 7. Neutral rest (45 frames ~ 1.5s)
        _append_frames(neutral_lm, 45)

        # 8. Ambiguous Brow + Smile Blend (11 frames ~ 360ms, non-command challenge)
        _append_frames(blend_lm, 11)

        # 9. Neutral rest (45 frames ~ 1.5s)
        _append_frames(neutral_lm, 45)

        # 10. Intentional Mouth Open 1 (11 frames ~ 360ms)
        mo1_start, mo1_end = _append_frames(mouth_lm, 11)

        # 11. Neutral rest (45 frames ~ 1.5s)
        _append_frames(neutral_lm, 45)

        # 12. Intentional Brow Raise 2 (11 frames ~ 360ms)
        br2_start, br2_end = _append_frames(brow_lm, 11)

        # 13. Neutral rest (45 frames ~ 1.5s)
        _append_frames(neutral_lm, 45)

        # 14. Intentional Smile 2 (11 frames ~ 360ms)
        sm2_start, sm2_end = _append_frames(smile_lm, 11)

        # 15. Neutral finish (60 frames ~ 2.0s)
        _append_frames(neutral_lm, 60)

        # Annotated ground truth events (5 intended commands)
        gts = [
            GroundTruthEvent(
                label="Brow Raise",
                start_ns=br1_start,
                end_ns=br1_end,
                annotator="test_suite",
                session_id="benchmark_suite_02",
            ),
            GroundTruthEvent(
                label="Smile / Lip Corner Pull",
                start_ns=sm1_start,
                end_ns=sm1_end,
                annotator="test_suite",
                session_id="benchmark_suite_02",
            ),
            GroundTruthEvent(
                label="Chin Raise / Mouth Open",
                start_ns=mo1_start,
                end_ns=mo1_end,
                annotator="test_suite",
                session_id="benchmark_suite_02",
            ),
            GroundTruthEvent(
                label="Brow Raise",
                start_ns=br2_start,
                end_ns=br2_end,
                annotator="test_suite",
                session_id="benchmark_suite_02",
            ),
            GroundTruthEvent(
                label="Smile / Lip Corner Pull",
                start_ns=sm2_start,
                end_ns=sm2_end,
                annotator="test_suite",
                session_id="benchmark_suite_02",
            ),
        ]

        # Execute replay
        report = replay.run_replay(
            packets, gts, is_synthetic=True, dataset_version="eval-benchmark-v2.0"
        )
        self._latest_report = report

        # Update UI table
        self.window.lab_view.update_metrics(
            report["condition_a"],
            report["condition_b"],
            report["condition_c"],
            ablations=report.get("ablations"),
            is_synthetic=True,
        )

    def _on_export_json(self) -> None:
        """Export latest benchmark report to JSON."""
        if hasattr(self, "_latest_report") and self._latest_report:
            from morph.evaluation.exporter import export_benchmark_json

            path = export_benchmark_json(self._latest_report)
            print(f"[Benchmark Exported]: {path}")

    def _on_export_csv(self) -> None:
        """Export latest benchmark report to CSV."""
        if hasattr(self, "_latest_report") and self._latest_report:
            from morph.evaluation.exporter import export_benchmark_csv

            path = export_benchmark_csv(self._latest_report)
            print(f"[CSV Exported]: {path}")

    def _on_settings_saved(self, new_config: RecognitionConfig) -> None:
        self.config = new_config
        self.intent_engine.config = new_config
        self.recognizer.min_similarity = new_config.min_similarity
        self.recognizer.min_margin = new_config.min_margin
        self.window.force_pause()

    def _on_worker_error(self, err: str) -> None:
        print(f"[MORPH Worker Error]: {err}")

    def run(self) -> int:
        self.window.show()
        # Always enforce startup state is PAUSED
        self.window.set_system_state(State.PAUSED)
        return self.app.exec()


def run_app() -> int:
    morph_app = MorphApplication()
    return morph_app.run()
