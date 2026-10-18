"""End-to-End UI Acceptance Tests for MORPH 2.0 (Journeys A through G).

Verifies true end-to-end integration between:
- PySide6 UI views (Studio, Settings, Board, Home, EvaluationSession)
- MorphApplication coordinator
- Intention gating state machine (IntentEngine)
- Personalized recognition (PersonalizedRecognizerB)
- Feature normalization and neutral baselines
- SQLite persistence (ProfileStore, ProfileVersionManager)
- Action dispatcher and hierarchical navigation
"""

from __future__ import annotations

import time

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from morph.actions.dispatcher import ConfirmedCommand
from morph.app import MorphApplication
from morph.common.types import (
    AnnotationSource,
    LandmarkPacket,
    State,
    TrackingHealth,
)
from morph.storage.db import DatabaseManager
from morph.storage.profiles import ProfileStore
from tests.fixtures.synthetic_faces import (
    create_synthetic_brow_raise_landmarks,
    create_synthetic_mouth_open_landmarks,
    create_synthetic_neutral_landmarks,
    create_synthetic_smile_landmarks,
)


@pytest.fixture(scope="module")
def qapp():
    """Ensure a singleton QApplication instance exists for offscreen Qt tests."""
    return QApplication.instance() or QApplication(["morph_test"])


@pytest.fixture
def test_env(tmp_path, qapp):
    """Create isolated application instance with temporary SQLite database."""
    db_path = str(tmp_path / "morph_test_e2e.db")
    db = DatabaseManager(db_path)
    store = ProfileStore(db)
    app = MorphApplication(no_camera=True, store=store)
    yield {
        "app": app,
        "store": store,
        "db": db,
        "window": app.window,
        "db_path": db_path,
    }
    app.close()
    db.close()


def _create_packet(
    landmarks: np.ndarray, frame_id: int, t_ns: int, valid: bool = True
) -> LandmarkPacket:
    """Helper to synthesize a LandmarkPacket."""
    return LandmarkPacket(
        frame_id=frame_id,
        t_ns=t_ns,
        face_count=1 if valid else 0,
        normalized_landmarks=landmarks if valid else None,
        blendshapes={},
        valid=valid,
        failure_reason="" if valid else "FACE_NOT_DETECTED",
    )


def test_journey_a_new_user_onboarding_to_execution(test_env):
    """Journey A: New user neutral calibration, gesture enrollment, redo, practice, and live dispatch."""
    app: MorphApplication = test_env["app"]
    win = app.window

    # 1. Initial State: Enforce startup state is PAUSED
    assert win._state == State.PAUSED
    assert app.intent_engine.state == State.PAUSED

    # 2. Navigate to Studio
    win.navigate_to_route("studio")
    assert win.stack.currentIndex() == 2

    # 3. Rest Baseline Calibration
    neutral_lm = create_synthetic_neutral_landmarks()
    pkt_neutral = _create_packet(neutral_lm, frame_id=1, t_ns=1_000_000_000)
    app._on_landmark_packet(pkt_neutral)

    # Click Calibrate Neutral
    win.studio_view.btn_neutral.click()
    assert "Calibrated successfully" in win.studio_view.lbl_neutral_status.text()
    assert app.normalizer.neutral_landmarks is not None
    assert app.store.get_neutral_baseline(app.active_profile_uuid) is not None

    # 4. Enroll Brow Raise (5 samples, test Redo on sample 5)
    brow_lm = create_synthetic_brow_raise_landmarks()
    pkt_brow = _create_packet(brow_lm, frame_id=2, t_ns=2_000_000_000)
    app._on_landmark_packet(pkt_brow)

    brow_row = win.studio_view.gesture_rows[0]
    assert brow_row["name"] == "Brow Raise"

    # Capture 5 samples
    for _ in range(5):
        brow_row["record_btn"].click()
    assert brow_row["sample_count"] == 5

    # Test Redo: removes 5th sample, count drops to 4
    brow_row["redo_btn"].click()
    assert brow_row["sample_count"] == 4
    # Re-capture to reach 5
    brow_row["record_btn"].click()
    assert brow_row["sample_count"] == 5

    # 5. Enroll Smile (5 samples)
    smile_lm = create_synthetic_smile_landmarks()
    pkt_smile = _create_packet(smile_lm, frame_id=3, t_ns=3_000_000_000)
    app._on_landmark_packet(pkt_smile)
    smile_row = win.studio_view.gesture_rows[1]
    assert smile_row["name"] == "Smile / Lip Corner Pull"
    for _ in range(5):
        smile_row["record_btn"].click()
    assert smile_row["sample_count"] == 5

    # 6. Enroll Mouth Open (5 samples) and map to BACK
    mouth_lm = create_synthetic_mouth_open_landmarks()
    pkt_mouth = _create_packet(mouth_lm, frame_id=4, t_ns=4_000_000_000)
    app._on_landmark_packet(pkt_mouth)
    mouth_row = win.studio_view.gesture_rows[2]
    assert mouth_row["name"] == "Chin Raise / Mouth Open"
    mouth_row["action_combo"].setCurrentText("BACK")
    for _ in range(5):
        mouth_row["record_btn"].click()
    assert mouth_row["sample_count"] == 5

    # 7. Save Trained Profile
    win.studio_view.btn_save.click()
    assert "Profile saved!" in win.studio_view.lbl_practice_feedback.text()

    # Verify recognizer trained and version created
    assert len(app.recognizer.prototypes) == 3
    versions = app.version_manager.list_versions(app.active_profile_uuid)
    assert len(versions) >= 1
    assert app.intent_engine.action_mappings["Chin Raise / Mouth Open"] == "BACK"

    # 8. Practice Mode (Zero Real External Side Effects)
    win.studio_view.btn_practice.click()
    assert app.dispatcher.mode == "PRACTICE"

    # In practice mode, stream brow raise frames
    now = 5_000_000_000
    for i in range(12):
        pkt = _create_packet(brow_lm, frame_id=10 + i, t_ns=now + i * 33_333_333)
        app._on_landmark_packet(pkt)

    assert "Candidate: <b>Brow Raise</b>" in win.studio_view.lbl_practice_feedback.text()
    assert win.board_view.current_index == 0  # Zero tile movement in practice mode!

    # Stop practice mode
    win.studio_view.btn_practice.click()
    assert app.dispatcher.mode == "LIVE"

    # 9. Live Mode Dispatch
    win.navigate_to_route("board")
    assert win.board_view.current_index == 0

    app.intent_engine.reset(State.IDLE)
    win.set_system_state(State.IDLE)

    # Stream Brow Raise in Live mode (> hold_ms = 250ms -> 12 frames @ 30fps = 400ms)
    now = 10_000_000_000
    for i in range(15):
        pkt = _create_packet(brow_lm, frame_id=50 + i, t_ns=now + i * 33_333_333)
        app._on_landmark_packet(pkt)

    # NEXT_TILE dispatched! Current board tile advanced from 0 to 1
    assert win.board_view.current_index == 1


def test_journey_b_restart_and_load_persistence(test_env):
    """Journey B: Application restart correctly restores baseline, weights, and mappings."""
    app: MorphApplication = test_env["app"]
    win = app.window
    store: ProfileStore = test_env["store"]

    # 1. Calibrate baseline and enroll 3 gestures in initial session
    neutral_lm = create_synthetic_neutral_landmarks()
    app._on_landmark_packet(_create_packet(neutral_lm, 1, 1_000_000_000))
    win.studio_view.btn_neutral.click()

    brow_lm = create_synthetic_brow_raise_landmarks()
    app._on_landmark_packet(_create_packet(brow_lm, 2, 2_000_000_000))
    for _ in range(5):
        win.studio_view.gesture_rows[0]["record_btn"].click()

    smile_lm = create_synthetic_smile_landmarks()
    app._on_landmark_packet(_create_packet(smile_lm, 3, 3_000_000_000))
    for _ in range(5):
        win.studio_view.gesture_rows[1]["record_btn"].click()

    mouth_lm = create_synthetic_mouth_open_landmarks()
    app._on_landmark_packet(_create_packet(mouth_lm, 4, 4_000_000_000))
    win.studio_view.gesture_rows[2]["action_combo"].setCurrentText("BACK")
    for _ in range(5):
        win.studio_view.gesture_rows[2]["record_btn"].click()

    win.studio_view.btn_save.click()

    # 2. Simulate fresh application launch with the same database
    new_app = MorphApplication(no_camera=True, store=store)
    try:
        # Check that baseline, weights, and mappings were loaded into runtime engines
        assert new_app.normalizer.neutral_landmarks is not None
        assert len(new_app.recognizer.prototypes) == 3
        assert new_app.intent_engine.action_mappings["Chin Raise / Mouth Open"] == "BACK"

        # Check that Studio view reflects stored sample counts
        for row in new_app.window.studio_view.gesture_rows:
            assert row["sample_count"] == 5
    finally:
        new_app.close()


def test_journey_c_recalibration_and_rollback(test_env):
    """Journey C: Parameter grid evaluation, promotion to candidate version, and safe rollback."""
    app: MorphApplication = test_env["app"]
    win = app.window

    # Setup baseline and gesture training first
    neutral_lm = create_synthetic_neutral_landmarks()
    app._on_landmark_packet(_create_packet(neutral_lm, 1, 1_000_000_000))
    win.studio_view.btn_neutral.click()

    brow_lm = create_synthetic_brow_raise_landmarks()
    app._on_landmark_packet(_create_packet(brow_lm, 2, 2_000_000_000))
    for _ in range(5):
        win.studio_view.gesture_rows[0]["record_btn"].click()

    smile_lm = create_synthetic_smile_landmarks()
    app._on_landmark_packet(_create_packet(smile_lm, 3, 3_000_000_000))
    for _ in range(5):
        win.studio_view.gesture_rows[1]["record_btn"].click()

    win.studio_view.btn_save.click()

    # Navigate to Settings
    win.navigate_to_route("settings")
    settings = win.settings_view

    # 1. Trigger Guided Calibration
    settings._on_evaluate_calibration()
    assert settings.btn_accept_candidate.isEnabled() is True
    assert settings.btn_reject_candidate.isEnabled() is True
    assert "Recommended Candidate" in settings.lbl_calibration_status.text()

    # 2. Promote candidate
    settings._on_accept_candidate()
    assert "Candidate promoted" in settings.lbl_calibration_status.text()

    # 3. Create another validated version to test multi-version rollback
    baseline = app.store.get_neutral_baseline(app.active_profile_uuid)
    assert baseline is not None
    neutral_lm, scale = baseline

    app.version_manager.create_version(
        profile_uuid=app.active_profile_uuid,
        weights=app.recognizer.to_dict(),
        thresholds={"hold_ms": 400, "cooldown_ms": 300},
        gesture_mappings={"Brow Raise": "NEXT_TILE"},
        neutral_landmarks=neutral_lm,
        interocular_ref=scale,
        validation_status="VALIDATED",
        notes="Candidate test version",
    )

    versions_before = app.version_manager.list_versions(app.active_profile_uuid)
    assert len(versions_before) >= 2

    # 4. Rollback to prior version
    settings._on_rollback()
    assert (
        "rolled back" in settings.lbl_calibration_status.text().lower()
        or "version" in settings.lbl_calibration_status.text().lower()
    )


def test_journey_d_research_session_recording_and_validation(test_env):
    """Journey D: Research trial recording, manual ground truth cue marker, and zero-residue wipe."""
    app: MorphApplication = test_env["app"]
    win = app.window

    win.navigate_to_route("session")
    session_view = win.eval_session_view

    # 1. Initialize trial session via consent gate
    session_view.txt_participant_id.setText("PART-9901")
    session_view.chk_consent.setChecked(True)
    assert session_view.session is not None
    assert session_view.session.participant_id == "PART-9901"

    # 2. Start stage and record feature packets
    session_view.btn_start_stage.click()
    assert session_view._stage_timer.isActive() is True

    # Stream landmark packets through coordinator
    neutral_lm = create_synthetic_neutral_landmarks()
    for i in range(10):
        pkt = _create_packet(neutral_lm, frame_id=200 + i, t_ns=20_000_000_000 + i * 33_333_333)
        app._on_landmark_packet(pkt)

    assert session_view._total_recorded_frames >= 10

    # 3. Fire ground truth cue
    session_view._on_fire_manual_cue()
    assert len(session_view.session.ground_truth_events) == 1
    evt = session_view.session.ground_truth_events[0]
    # Invariant: Prompt cue marker must have start_ns == end_ns (point marker, zero fabricated duration)
    assert evt.start_ns == evt.end_ns
    assert evt.annotation_source == AnnotationSource.TASK_PROMPT

    # 4. Zero-residue participant withdrawal
    s_uuid = session_view.session.session_uuid
    session_view._discard_session()
    assert session_view.session is None
    # Verify zero database residue
    row = app.store.db.fetch_one(
        "SELECT session_uuid FROM evaluation_sessions WHERE session_uuid = ?;", (s_uuid,)
    )
    assert row is None


def test_journey_e_camera_disconnect_fail_close_and_rearm(test_env):
    """Journey E: Camera disconnect causes immediate fail-closed TRACKING_LOST and safe re-arm."""
    app: MorphApplication = test_env["app"]
    win = app.window

    # Set up LIVE state
    app.intent_engine.reset(State.IDLE)
    win.set_system_state(State.IDLE)

    # 1. Simulate camera disconnection telemetry
    disc_health = TrackingHealth(
        processed_fps=0.0,
        capture_fps=0.0,
        dropped_frames=10,
        stale_frames=5,
        face_count=0,
        last_block_reason="DEVICE_DISCONNECTED",
        camera_connected=False,
    )
    app._on_worker_health(disc_health)

    # System immediately drops to TRACKING_LOST
    assert app.intent_engine.state == State.TRACKING_LOST
    assert win._state == State.TRACKING_LOST

    # In TRACKING_LOST, invalid landmark packets must produce zero commands
    base_t = time.monotonic_ns() + 1_000_000_000
    inv_pkt = _create_packet(np.zeros((478, 3)), frame_id=999, t_ns=base_t, valid=False)
    app._on_landmark_packet(inv_pkt)
    assert app.intent_engine.state == State.TRACKING_LOST

    # 2. Camera reconnects and user returns to neutral pose
    recon_health = TrackingHealth(
        processed_fps=30.0,
        capture_fps=30.0,
        dropped_frames=0,
        stale_frames=0,
        face_count=1,
        last_block_reason="",
        camera_connected=True,
    )
    app._on_worker_health(recon_health)

    neutral_lm = create_synthetic_neutral_landmarks()
    # Stream 10 neutral frames (300ms) for re-arm dwell
    for i in range(10):
        t = base_t + 100_000_000 + i * 33_333_333
        pkt = _create_packet(neutral_lm, frame_id=1000 + i, t_ns=t, valid=True)
        app._on_landmark_packet(pkt)

    # System safely re-arms to IDLE
    assert app.intent_engine.state == State.IDLE
    assert win._state == State.IDLE


def test_journey_f_board_actions_and_back_navigation(test_env):
    """Journey F: Board actions dispatch correctly and BACK navigates to home view."""
    app: MorphApplication = test_env["app"]
    win = app.window

    # Navigate to Board view
    win.navigate_to_route("board")
    assert win.stack.currentIndex() == 3

    # Dispatch NEXT_TILE
    cmd_next = ConfirmedCommand(
        command_event_uuid="cmd-1",
        frame_id=1,
        confirmed_at_ns=1000,
        gesture_uuid="g1",
        action_mapping_uuid="NEXT_TILE",
        version_snapshot="v1",
    )
    app.dispatcher.dispatch(cmd_next)
    assert win.board_view.current_index == 1

    # Dispatch SELECT_TILE
    cmd_select = ConfirmedCommand(
        command_event_uuid="cmd-2",
        frame_id=2,
        confirmed_at_ns=2000,
        gesture_uuid="g2",
        action_mapping_uuid="SELECT_TILE",
        version_snapshot="v1",
    )
    app.dispatcher.dispatch(cmd_select)
    assert win.board_view.spoken_banner.text() != ""

    # Dispatch BACK action -> Must navigate back to home screen (index 0)
    cmd_back = ConfirmedCommand(
        command_event_uuid="cmd-3",
        frame_id=3,
        confirmed_at_ns=3000,
        gesture_uuid="g3",
        action_mapping_uuid="BACK",
        version_snapshot="v1",
    )
    app.dispatcher.dispatch(cmd_back)
    assert win.stack.currentIndex() == 0  # Successfully returned to Home!


def test_journey_g_settings_evaluation_with_calibrator(test_env):
    """Journey G: Settings parameter grid evaluation uses stored samples and UserParameterCalibrator."""
    app: MorphApplication = test_env["app"]
    win = app.window

    # Set up baseline and gesture samples
    neutral_lm = create_synthetic_neutral_landmarks()
    app._on_landmark_packet(_create_packet(neutral_lm, 1, 1_000_000_000))
    win.studio_view.btn_neutral.click()

    brow_lm = create_synthetic_brow_raise_landmarks()
    app._on_landmark_packet(_create_packet(brow_lm, 2, 2_000_000_000))
    for _ in range(5):
        win.studio_view.gesture_rows[0]["record_btn"].click()

    smile_lm = create_synthetic_smile_landmarks()
    app._on_landmark_packet(_create_packet(smile_lm, 3, 3_000_000_000))
    for _ in range(5):
        win.studio_view.gesture_rows[1]["record_btn"].click()

    win.studio_view.btn_save.click()

    # Run parameter evaluation through coordinator
    app._on_evaluate_parameters()

    # Verify settings view displays candidate recommendation
    settings = app.window.settings_view
    assert settings.btn_accept_candidate.isEnabled() is True
    assert settings.btn_reject_candidate.isEnabled() is True
    assert "Recommended Candidate" in settings.lbl_calibration_status.text()
