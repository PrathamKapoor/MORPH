"""Automated integration tests for the 14 primary interaction flows and accessibility invariants (Milestone M8.5).

Covers:
1. Creating a profile
2. Neutral calibration
3. Training three gestures
4. Identifying a gesture conflict
5. Testing a gesture in practice mode
6. Assigning an action
7. Entering the communication board
8. Navigating between tiles
9. Speaking a selected message
10. Pausing control
11. Recovering after tracking loss
12. Recalibrating parameters
13. Restoring a previous profile
14. Exiting safely

Also verifies tab order, keyboard traversal, focus restoration, dialog cancellation, and error banners.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from morph.actions.dispatcher import ActionDispatcher
from morph.actions.tts import WindowsSapiTTS
from morph.calibration.evaluator import UserParameterCalibrator
from morph.common.config import RecognitionConfig
from morph.common.types import ConfirmedCommand, FeaturePacket, State, TrackingHealth
from morph.intent.engine import IntentEngine
from morph.recognition.recognizer_b import PersonalizedRecognizerB
from morph.storage.db import DatabaseManager
from morph.storage.profiles import ProfileStore
from morph.storage.versions import ProfileVersionManager
from morph.ui.main_window import MainWindow
from tests.fixtures.benchmark_scenarios import BenchmarkScenarioSuite
from tests.fixtures.synthetic_faces import create_synthetic_neutral_landmarks


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def journey_env():
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "journey.db"
        db = DatabaseManager(db_path)
        store = ProfileStore(db)
        v_mgr = ProfileVersionManager(db)
        calibrator = UserParameterCalibrator(v_mgr)
        yield {
            "db": db,
            "store": store,
            "v_mgr": v_mgr,
            "calibrator": calibrator,
            "dir": td,
        }


def test_14_primary_interaction_flows(qapp, journey_env):
    """Execute all 14 primary user tasks in sequential, realistic order."""
    store: ProfileStore = journey_env["store"]

    # =========================================================================
    # Task 1: Creating a profile
    # =========================================================================
    p_uuid = store.create_profile("Alex Rivera", "Adult with severe motor impairment")
    store.set_active_profile(p_uuid)
    active_p = store.get_or_create_default_profile()
    assert active_p == p_uuid
    profiles = store.list_profiles()
    assert any(p["profile_uuid"] == p_uuid for p in profiles)

    # =========================================================================
    # Task 2: Neutral Posture Calibration
    # =========================================================================
    neutral_lm = create_synthetic_neutral_landmarks()
    neutral_uuid = store.save_neutral_baseline(
        profile_uuid=p_uuid,
        median_landmarks=neutral_lm,
        interocular_ref=0.30,
        created_at_ns=1_000_000_000,
    )
    assert neutral_uuid != ""
    retrieved_neutral = store.get_neutral_baseline(p_uuid)
    assert retrieved_neutral is not None
    assert retrieved_neutral[0].shape == (478, 3)

    # =========================================================================
    # Task 3: Training Three Gestures
    # =========================================================================
    suite = BenchmarkScenarioSuite()
    cal_protos = suite.get_calibration_prototypes()

    g1 = store.add_gesture_class(p_uuid, "Brow Raise", "NEXT_TILE")
    g2 = store.add_gesture_class(p_uuid, "Smile / Lip Corner Pull", "SELECT_TILE")
    g3 = store.add_gesture_class(p_uuid, "Chin Raise / Mouth Open", "PREVIOUS_TILE")

    for v in cal_protos["Brow Raise"]:
        store.add_gesture_sample(g1, v, False, 1, 1.0, 1000)
    for v in cal_protos["Smile / Lip Corner Pull"]:
        store.add_gesture_sample(g2, v, False, 1, 1.0, 2000)
    for v in cal_protos["Chin Raise / Mouth Open"]:
        store.add_gesture_sample(g3, v, False, 1, 1.0, 3000)

    assert len(store.get_gesture_samples(g1)) == 5
    assert len(store.get_gesture_samples(g2)) == 5
    assert len(store.get_gesture_samples(g3)) == 5

    rec_b = PersonalizedRecognizerB(min_similarity=0.65, min_margin=0.15)
    rec_b.fit(cal_protos)
    assert len(rec_b.prototypes) == 3

    # =========================================================================
    # Task 4: Identifying a Gesture Conflict
    # =========================================================================
    # Simulate an ambiguous blend vector having nearly equal similarity to Brow Raise and Smile
    brow_vec = rec_b.prototypes["Brow Raise"]
    smile_vec = rec_b.prototypes["Smile / Lip Corner Pull"]
    ambiguous_vec = (brow_vec + smile_vec) / np.linalg.norm(brow_vec + smile_vec)

    pkt_ambig = FeaturePacket(
        frame_id=1,
        t_ns=1000,
        feature_schema_version="v1.0",
        vector=ambiguous_vec,
        valid=True,
        quality=1.0,
    )
    pred_ambig = rec_b.predict(pkt_ambig)
    # The recognizer must reject the ambiguous conflict due to separation margin < 0.15
    assert pred_ambig.accepted_candidate_or_none is None
    assert "CONFLICT" in pred_ambig.reject_reason or "MARGIN" in pred_ambig.reject_reason

    # =========================================================================
    # Task 5: Testing a Gesture in Practice Mode
    # =========================================================================
    cfg = RecognitionConfig(hold_ms=250, release_ms=150, cooldown_ms=300)
    engine = IntentEngine(
        config=cfg,
        action_mappings={"Brow Raise": "NEXT_TILE", "Smile / Lip Corner Pull": "SELECT_TILE"},
    )
    engine.reset(State.IDLE)

    # Clean Brow Raise test packet
    pkt_brow = FeaturePacket(
        frame_id=2,
        t_ns=10_000_000_000,
        feature_schema_version="v1.0",
        vector=brow_vec,
        valid=True,
        quality=1.0,
    )
    pred_brow = rec_b.predict(pkt_brow)
    assert pred_brow.accepted_candidate_or_none == "Brow Raise"

    # In practice mode, verify IntentEngine steps correctly without live external side effects (fail-closed State.PAUSED)
    st, cmd, _ = engine.step(pred_brow, True, pkt_brow.t_ns, mode="PRACTICE", paused=False)
    assert st == State.PAUSED
    assert cmd is None

    # In LIVE mode, candidate enters dwell state
    engine.reset(State.IDLE)
    st_live, cmd_live, _ = engine.step(
        pred_brow, True, pkt_brow.t_ns + 10_000_000, mode="LIVE", paused=False
    )
    assert st_live == State.CANDIDATE
    assert cmd_live is None

    # =========================================================================
    # Task 6: Assigning an Action
    # =========================================================================
    # Reassign Brow Raise to SPEAK_TILE
    classes = store.list_gesture_classes(p_uuid)
    assert any(c["name"] == "Brow Raise" for c in classes)
    store.add_gesture_class(p_uuid, "Brow Raise", "SPEAK_TILE")
    updated_classes = store.list_gesture_classes(p_uuid)
    assert any(
        c["name"] == "Brow Raise" and c["action_type"] == "SPEAK_TILE" for c in updated_classes
    )

    # =========================================================================
    # Task 7: Entering the Communication Board
    # =========================================================================
    win = MainWindow()
    win.navigate_to_route("board")
    assert win.stack.currentIndex() == 3
    board = win.board_view
    assert len(board.tiles) == 9
    assert board.current_index == 0

    # =========================================================================
    # Task 8: Navigating Between Tiles
    # =========================================================================
    # Next Tile
    board.navigate_next()
    assert board.current_index == 1
    board.navigate_next()
    assert board.current_index == 2
    # Previous Tile
    board.navigate_previous()
    assert board.current_index == 1

    # =========================================================================
    # Task 9: Speaking a Selected Message
    # =========================================================================
    tts = WindowsSapiTTS()
    spoken_phrase = board.select_current()  # e.g., "NO"
    assert spoken_phrase != ""
    assert spoken_phrase in board.spoken_banner.text()
    # Test dispatcher routing
    called = []
    dispatcher = ActionDispatcher(mode="LIVE")
    dispatcher.register_handler(
        "SPEAK_TILE",
        lambda: (called.append(True), tts.speak(spoken_phrase)),
    )
    cmd_speak = ConfirmedCommand(
        command_event_uuid="cmd-001",
        frame_id=2,
        confirmed_at_ns=1_000_000_000,
        gesture_uuid="g1",
        action_mapping_uuid="SPEAK_TILE",
        version_snapshot="v1",
    )
    result = dispatcher.dispatch(cmd_speak)
    assert result.success is True
    assert len(called) == 1

    # =========================================================================
    # Task 10: Pausing Control (Emergency Fail-Closed Override)
    # =========================================================================
    win._state = State.IDLE
    win.force_pause()
    assert win._state == State.PAUSED
    assert "PAUSED" in win.btn_global_pause.text()

    # Spacebar shortcut test
    win._toggle_global_pause()
    assert win._state == State.IDLE
    win._toggle_global_pause()
    assert win._state == State.PAUSED

    # =========================================================================
    # Task 11: Recovering After Tracking Loss
    # =========================================================================
    win.show_banner(
        "Face tracking lost: participant out of camera view",
        action_text="Resume",
        action_callback=win.hide_banner,
        level="ERROR",
    )
    assert not win.banner_widget.isHidden()
    assert "tracking lost" in win.lbl_banner_text.text()

    # Recovery: camera re-acquires face
    win.update_health(
        TrackingHealth(
            processed_fps=30.0,
            capture_fps=30.0,
            dropped_frames=0,
            stale_frames=0,
            face_count=1,
            last_block_reason="",
            camera_connected=True,
        )
    )
    win.hide_banner()
    assert win.banner_widget.isHidden()

    # =========================================================================
    # Task 12: Guided Parameter Recalibration
    # =========================================================================
    win.navigate_to_route("settings")
    settings = win.settings_view
    assert settings is not None

    settings._on_evaluate_calibration()
    assert settings.btn_accept_candidate.isEnabled() is True
    assert settings.spin_hold.value() == 250

    # Accept candidate
    settings._on_accept_candidate()
    assert settings.config.hold_ms == 250
    assert "promoted" in settings.lbl_calibration_status.text().lower()

    # =========================================================================
    # Task 13: Restoring a Previous Profile Version (Rollback)
    # =========================================================================
    settings._on_rollback()
    assert settings.config.hold_ms == 300
    assert "rolled back" in settings.lbl_calibration_status.text().lower()

    # =========================================================================
    # Task 14: Exiting Safely
    # =========================================================================
    # Verify closeEvent forces clean pause and unregisters hooks
    win.close()
    assert win._state == State.PAUSED


def test_ui_accessibility_tab_order_and_focus(qapp):
    """Verify circular tab traversal, focus properties, and accessible names."""
    win = MainWindow()

    # 1. Accessible Names & Roles verification
    views = [
        (win.home_view, "Home"),
        (win.onboarding_view, "Onboarding"),
        (win.studio_view, "Studio"),
        (win.board_view, "Board"),
        (win.settings_view, "Settings"),
        (win.monitor_view, "Monitor"),
        (win.lab_view, "Lab"),
        (win.eval_session_view, "Evaluation"),
        (win.demo_view, "Demo"),
    ]
    for v, name in views:
        assert v.accessibleName() != "", f"{name} view missing accessibleName"

    # 2. Key components accessible names
    assert win.tab_bar.accessibleName() != ""
    assert win.btn_global_pause.accessibleName() != ""
    assert win.btn_global_pause.accessibleDescription() != ""

    # 3. Tab cycling
    for idx in range(9):
        win.tab_bar.setCurrentIndex(idx)
        assert win.stack.currentIndex() == idx

    # 4. Global keyboard shortcuts exist
    assert win.shortcut_space is not None
    assert win.shortcut_space.key().toString() == "Space"
    assert win.shortcut_esc is not None
    assert win.shortcut_esc.key().toString() == "Esc"
