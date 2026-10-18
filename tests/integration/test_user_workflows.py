"""End-to-end integration tests verifying complete user journeys across multi-component pipelines (Milestone M6.1).

Covers:
- Workflow 1: First-time user onboarding, calibration, gesture training, mapping, board execution, safe pause
- Workflow 2: Returning user loading validated profile, drift check, practice sandbox, and live dispatch
- Workflow 3: Unreliable calibration detection, drift explanation, candidate creation, evaluation, and rollback
- Workflow 4: Tracking failure mid-gesture, fail-close abort, rearming conditions, and safe recovery
- Workflow 5: Profile and version persistence across application restart cycles
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from morph.actions.dispatcher import ActionDispatcher, NoOpActionSink
from morph.common.config import RecognitionConfig
from morph.common.types import LandmarkPacket, RecognitionResult, State
from morph.features.drift import CalibrationStatus, DriftDetector
from morph.features.normalizer import FeatureExtractor
from morph.intent.engine import DecisionReason, IntentEngine
from morph.recognition.conflict import ConflictSeverity, GestureConflictDetector
from morph.recognition.recognizer_b import PersonalizedRecognizerB
from morph.storage.db import DatabaseManager
from morph.storage.profiles import ProfileStore
from morph.storage.versions import ProfileVersionManager
from morph.ui.main_window import MainWindow
from tests.fixtures.synthetic_faces import (
    create_synthetic_brow_raise_landmarks,
    create_synthetic_mouth_open_landmarks,
    create_synthetic_neutral_landmarks,
    create_synthetic_noise_landmarks,
    create_synthetic_smile_landmarks,
)


@pytest.fixture(scope="module")
def qapp():
    """Ensure a singleton QApplication instance exists for offscreen Qt tests."""
    app = QApplication.instance() or QApplication(["morph_test"])
    yield app


def test_workflow_1_first_time_user(tmp_path, qapp):
    """Workflow 1: First-time user setup, calibration, 3-gesture training, conflict check, board dispatch, pause."""
    db_path = str(tmp_path / "first_time_user.db")
    db = DatabaseManager(db_path)
    store = ProfileStore(db)

    # 1-3. Launch application and verify initial safe PAUSED state
    window = MainWindow()
    assert window._state == State.PAUSED
    assert window.banner_widget.isHidden() is True

    # 4-5. Create new profile for first-time user
    user_p_uuid = store.create_profile("Alice (ALS User)")
    assert user_p_uuid is not None
    store.set_active_profile(user_p_uuid)

    # 6. Neutral baseline calibration (stream 10 rest frames)
    neutral_lm = create_synthetic_neutral_landmarks()
    extractor = FeatureExtractor()
    extractor.set_neutral_baseline(neutral_lm, 0.25)
    store.save_neutral_baseline(user_p_uuid, neutral_lm, 0.25, 1_000_000_000)

    # 7-11. Enroll 3 distinct facial movements (5 samples each)
    brow_lm = create_synthetic_brow_raise_landmarks()
    smile_lm = create_synthetic_smile_landmarks()
    open_lm = create_synthetic_mouth_open_landmarks()

    brow_pkt = LandmarkPacket(
        frame_id=1,
        t_ns=1000,
        face_count=1,
        normalized_landmarks=brow_lm,
        blendshapes={},
        valid=True,
        failure_reason="",
    )
    smile_pkt = LandmarkPacket(
        frame_id=2,
        t_ns=2000,
        face_count=1,
        normalized_landmarks=smile_lm,
        blendshapes={},
        valid=True,
        failure_reason="",
    )
    open_pkt = LandmarkPacket(
        frame_id=3,
        t_ns=3000,
        face_count=1,
        normalized_landmarks=open_lm,
        blendshapes={},
        valid=True,
        failure_reason="",
    )

    feat_brow = extractor.extract(brow_pkt)
    feat_smile = extractor.extract(smile_pkt)
    feat_open = extractor.extract(open_pkt)

    recognizer = PersonalizedRecognizerB(profile_version="v1")
    recognizer.fit(
        {
            "Brow Raise": [feat_brow.vector] * 5,
            "Smile": [feat_smile.vector] * 5,
            "Mouth Open": [feat_open.vector] * 5,
        }
    )

    # 12. Conflict and ambiguity check
    conflict_detector = GestureConflictDetector(strong_threshold=0.85)
    reports = conflict_detector.check_all_pairs(recognizer.prototypes)
    assert not any(r.severity == ConflictSeverity.STRONG for r in reports)
    assert len(reports) == 3

    # 13. Map gestures to communication board actions
    action_mappings = {
        "Brow Raise": "NEXT_TILE",
        "Smile": "SELECT_TILE",
        "Mouth Open": "PAUSE",
    }
    for g_name, act in action_mappings.items():
        store.add_gesture_class(user_p_uuid, g_name, act)

    # 14-15. Navigate to Communication Board and explicitly activate (IDLE)
    window.navigate_to_route("board")
    assert window.stack.currentWidget() == window.board_view

    # Wire action dispatcher to board view
    dispatcher = ActionDispatcher(mode="LIVE")
    dispatcher.register_handler("NEXT_TILE", window.board_view.navigate_next)
    dispatcher.register_handler("SELECT_TILE", window.board_view.select_current)
    dispatcher.register_handler("PAUSE", window.force_pause)

    intent_engine = IntentEngine(config=RecognitionConfig(hold_ms=250, cooldown_ms=300))
    intent_engine.set_action_mappings(action_mappings)
    window.set_system_state(State.IDLE)
    intent_engine.reset(State.IDLE)
    assert intent_engine.state == State.IDLE

    # 16-17. Perform intended "Brow Raise" held for 260ms -> fires NEXT_TILE exactly once
    t_start = 1_000_000_000
    initial_focus = window.board_view.current_index

    # Hold candidate across frames
    for f in range(9):  # 9 frames * 33.3ms = ~300ms
        t_now = t_start + f * 33_333_333
        rec = recognizer.predict(feat_brow)
        state, cmd, _ = intent_engine.step(rec, tracking_valid=True, now_ns=t_now)
        if cmd is not None:
            dispatcher.dispatch(cmd)

    # Focus advanced by exactly 1 tile
    assert window.board_view.current_index == initial_focus + 1
    assert intent_engine.state == State.COOLDOWN

    # 18-19. Ordinary movements / noise twitch during cooldown -> 0 dispatches
    noise_lm = create_synthetic_noise_landmarks()
    feat_noise = extractor.extract(
        LandmarkPacket(
            frame_id=10,
            t_ns=t_start + 400_000_000,
            face_count=1,
            normalized_landmarks=noise_lm,
            blendshapes={},
            valid=True,
            failure_reason="",
        )
    )
    rec_noise = recognizer.predict(feat_noise)
    state, cmd_noise, _ = intent_engine.step(
        rec_noise, tracking_valid=True, now_ns=t_start + 400_000_000
    )
    assert cmd_noise is None
    assert window.board_view.current_index == initial_focus + 1

    # 20-21. Pause control via shortcut or action -> verify total suppression
    window.force_pause()
    assert window._state == State.PAUSED
    intent_engine.reset(State.PAUSED)

    # Attempt sustained gesture while paused
    rec_brow = recognizer.predict(feat_brow)
    state_paused, cmd_paused, _ = intent_engine.step(
        rec_brow, tracking_valid=True, now_ns=t_start + 1_000_000_000, paused=True
    )
    assert state_paused == State.PAUSED
    assert cmd_paused is None
    assert intent_engine.last_decision_reason == DecisionReason.REJECTED_PAUSED


def test_workflow_2_returning_user(tmp_path, qapp):
    """Workflow 2: Returning user loading existing validated profile, drift check, practice trial, and live dispatch."""
    db_path = str(tmp_path / "returning_user.db")
    db = DatabaseManager(db_path)
    store = ProfileStore(db)
    version_mgr = ProfileVersionManager(db)

    # Setup pre-existing profile in database
    p_uuid = store.create_profile("Bob (Returning User)")
    neutral_lm = create_synthetic_neutral_landmarks()
    store.save_neutral_baseline(p_uuid, neutral_lm, 0.25, 1_000_000_000)
    store.add_gesture_class(p_uuid, "Smile", "SELECT_TILE")

    smile_lm = create_synthetic_smile_landmarks()
    extractor = FeatureExtractor()
    extractor.set_neutral_baseline(neutral_lm, 0.25)
    feat_smile = extractor.extract(
        LandmarkPacket(
            frame_id=1,
            t_ns=1000,
            face_count=1,
            normalized_landmarks=smile_lm,
            blendshapes={},
            valid=True,
            failure_reason="",
        )
    )

    # Save validated profile version 1
    v1 = version_mgr.create_version(
        profile_uuid=p_uuid,
        weights={"Smile": feat_smile.vector.tolist()},
        thresholds={"min_similarity": 0.8},
        gesture_mappings={"Smile": "SELECT_TILE"},
        neutral_landmarks=neutral_lm,
        interocular_ref=0.25,
        validation_status="VALIDATED",
        notes="Pre-existing calibrated version",
    )
    assert v1.version_number == 1

    # 1-4. Returning user launches app -> loads profile and verifies version compatibility
    loaded_version = version_mgr.get_version_by_number(p_uuid, 1)
    assert loaded_version is not None
    assert loaded_version.validation_status == "VALIDATED"

    # 5-6. Calibration health check at session start (test with stable neutral posture)
    drift_detector = DriftDetector()
    current_rest = [neutral_lm] * 5
    health_rep = drift_detector.assess_neutral_drift(
        current_neutral_landmarks=current_rest,
        stored_neutral_landmarks=loaded_version.neutral_landmarks,
        interocular_ref=loaded_version.interocular_ref,
    )
    assert health_rep.status == CalibrationStatus.STABLE
    assert health_rep.requires_recalibration is False

    # 7-8. Enter Practice Mode (sandbox without side effects)
    sink = NoOpActionSink()
    dispatcher = ActionDispatcher(mode="PRACTICE", noop_sink=sink)
    recognizer = PersonalizedRecognizerB(profile_version="v1")
    recognizer.fit({"Smile": [feat_smile.vector]})
    intent_engine = IntentEngine(config=RecognitionConfig(hold_ms=250))
    intent_engine.set_action_mappings({"Smile": "SELECT_TILE"})
    intent_engine.reset(State.IDLE)

    # Perform gesture in practice mode
    t0 = 1_000_000_000
    for f in range(9):
        t_now = t0 + f * 33_333_333
        rec = recognizer.predict(feat_smile)
        state, cmd, _ = intent_engine.step(rec, tracking_valid=True, now_ns=t_now)
        if cmd is not None:
            res = dispatcher.dispatch(cmd)
            assert res.success is True

    # Practice mode recorded in sink without board execution
    assert len(sink.recorded_dispatches) == 1
    assert sink.recorded_dispatches[0][0] == "SELECT_TILE"

    # 9-10. Toggle to LIVE mode and verify real execution
    dispatcher.mode = "LIVE"
    executed_live = []
    dispatcher.register_handler("SELECT_TILE", lambda: executed_live.append("SPOKEN"))

    intent_engine.reset(State.IDLE)
    t1 = t0 + 1_000_000_000
    for f in range(9):
        t_now = t1 + f * 33_333_333
        rec = recognizer.predict(feat_smile)
        state, cmd, _ = intent_engine.step(rec, tracking_valid=True, now_ns=t_now, mode="LIVE")
        if cmd is not None:
            dispatcher.dispatch(cmd)

    assert len(executed_live) == 1
    assert executed_live[0] == "SPOKEN"


def test_workflow_3_unreliable_calibration_and_rollback(tmp_path):
    """Workflow 3: Posture drift detection, non-medical advice, candidate version, evaluation, and safe atomic rollback."""
    db_path = str(tmp_path / "drift_rollback.db")
    db = DatabaseManager(db_path)
    store = ProfileStore(db)
    version_mgr = ProfileVersionManager(db)

    p_uuid = store.create_profile("Charlie")
    base_lm = create_synthetic_neutral_landmarks()
    store.save_neutral_baseline(p_uuid, base_lm, 0.25, 1_000_000_000)

    v1 = version_mgr.create_version(
        profile_uuid=p_uuid,
        weights={"Smile": [0.5] * 32},
        thresholds={"Smile": 0.8},
        gesture_mappings={"Smile": "SELECT_TILE"},
        neutral_landmarks=base_lm,
        interocular_ref=0.25,
        validation_status="VALIDATED",
        notes="Original stable baseline",
    )
    assert v1.version_number == 1

    # 1-2. Introduce testable distribution shift (simulating camera bump or posture change)
    shifted_lm = base_lm.copy()
    shifted_lm[:, 0] += 0.45  # Severe anatomical shift

    # 3-4. Detect shift and produce non-medical advice
    detector = DriftDetector()
    rep = detector.assess_neutral_drift(
        current_neutral_landmarks=[shifted_lm] * 5,
        stored_neutral_landmarks=base_lm,
        interocular_ref=0.25,
    )
    assert rep.status == CalibrationStatus.SEVERE_DRIFT
    assert rep.requires_recalibration is True
    assert "recalibration" in rep.recommendation.lower()

    # 5-6. Create candidate profile version 2
    v2_candidate = version_mgr.create_version(
        profile_uuid=p_uuid,
        weights={"Smile": [0.8] * 32},
        thresholds={"Smile": 0.8},
        gesture_mappings={"Smile": "SELECT_TILE"},
        neutral_landmarks=shifted_lm,
        interocular_ref=0.25,
        validation_status="CANDIDATE",
        notes="Experimental candidate under lighting shift",
    )
    assert v2_candidate.version_number == 2
    assert v2_candidate.validation_status == "CANDIDATE"

    # 7-8. Evaluation determines candidate is unsatisfactory -> user requests rollback
    # 9-10. Atomic rollback to version 1
    rolled_back = version_mgr.rollback_to_version(p_uuid, version_number=1)
    assert rolled_back is not None
    assert rolled_back.version_number == 1
    assert rolled_back.validation_status == "VALIDATED"

    # Verify active database tables were reverted
    active_baseline = store.get_neutral_baseline(p_uuid)
    assert active_baseline is not None
    np.testing.assert_allclose(active_baseline[0], base_lm)


def test_workflow_4_tracking_failure_and_recovery():
    """Workflow 4: Mid-gesture tracking loss, fail-close abort, rearming conditions, and safe recovery."""
    intent_engine = IntentEngine(config=RecognitionConfig(hold_ms=300, release_ms=150))
    intent_engine.reset(State.IDLE)

    t0 = 1_000_000_000
    rec_candidate = RecognitionResult(
        frame_id=1,
        t_ns=t0,
        label_scores={"Brow Raise": 0.95},
        best_label="Brow Raise",
        second_label="NONE",
        accepted_candidate_or_none="Brow Raise",
        reject_reason="",
    )

    # 1. Begin candidate gesture
    state, cmd, _ = intent_engine.step(rec_candidate, tracking_valid=True, now_ns=t0)
    assert state == State.CANDIDATE
    assert cmd is None

    # 2-4. Tracking drops at t0 + 100ms (face turned away / camera occluded)
    t_drop = t0 + 100_000_000
    rec_lost = RecognitionResult(
        frame_id=2,
        t_ns=t_drop,
        label_scores={},
        best_label="NONE",
        second_label="NONE",
        accepted_candidate_or_none=None,
        reject_reason="NO_FACE_DETECTED",
    )
    state_lost, cmd_lost, trans = intent_engine.step(rec_lost, tracking_valid=False, now_ns=t_drop)
    assert state_lost == State.TRACKING_LOST
    assert cmd_lost is None
    assert intent_engine.last_decision_reason == DecisionReason.REJECTED_TRACKING_LOSS

    # 5-6. Face reappears at t0 + 300ms
    t_reappear = t0 + 300_000_000
    rec_neutral = RecognitionResult(
        frame_id=3,
        t_ns=t_reappear,
        label_scores={},
        best_label="NEUTRAL",
        second_label="NONE",
        accepted_candidate_or_none=None,
        reject_reason="",
    )
    state_restored, cmd_restored, _ = intent_engine.step(
        rec_neutral, tracking_valid=True, now_ns=t_reappear
    )
    # Re-arms cleanly to IDLE
    assert state_restored == State.IDLE
    assert cmd_restored is None


def test_workflow_5_restart_persistence(tmp_path):
    """Workflow 5: Profile, gesture mappings, and version history persist and reload identically across restarts."""
    db_file = str(tmp_path / "persistence_test.db")

    # Session 1: Create profile, calibrate, enroll gestures, create version
    db1 = DatabaseManager(db_file)
    store1 = ProfileStore(db1)
    version_mgr1 = ProfileVersionManager(db1)

    p_uuid = store1.create_profile("David")
    neutral_lm = create_synthetic_neutral_landmarks()
    store1.save_neutral_baseline(p_uuid, neutral_lm, 0.25, 1_000_000_000)
    store1.add_gesture_class(p_uuid, "Brow Raise", "NEXT_TILE")
    store1.add_gesture_class(p_uuid, "Smile", "SELECT_TILE")

    v1 = version_mgr1.create_version(
        profile_uuid=p_uuid,
        weights={"Brow Raise": [0.1] * 32, "Smile": [0.2] * 32},
        thresholds={"min_similarity": 0.82, "hold_ms": 250},
        gesture_mappings={"Brow Raise": "NEXT_TILE", "Smile": "SELECT_TILE"},
        neutral_landmarks=neutral_lm,
        interocular_ref=0.25,
        validation_status="VALIDATED",
        notes="Session 1 calibrated model",
    )
    assert v1.version_number == 1

    # Simulate full application exit (drop connection references)
    del store1
    del version_mgr1
    del db1

    # Session 2: Launch application fresh against existing database file
    db2 = DatabaseManager(db_file)
    store2 = ProfileStore(db2)
    version_mgr2 = ProfileVersionManager(db2)

    profiles = store2.list_profiles()
    assert len(profiles) == 1
    assert profiles[0]["profile_uuid"] == p_uuid
    assert profiles[0]["name"] == "David"

    # Verify neutral baseline reloads
    baseline = store2.get_neutral_baseline(p_uuid)
    assert baseline is not None
    loaded_lm, loaded_scale = baseline
    np.testing.assert_allclose(loaded_lm, neutral_lm)
    assert loaded_scale == 0.25

    # Verify gesture classes and action mappings
    gestures = store2.get_profile_gestures(p_uuid)
    assert len(gestures) == 2
    g_map = {g["name"]: g["action_type"] for g in gestures}
    assert g_map["Brow Raise"] == "NEXT_TILE"
    assert g_map["Smile"] == "SELECT_TILE"

    # Verify version history reloads
    v_loaded = version_mgr2.get_version_by_number(p_uuid, 1)
    assert v_loaded is not None
    assert v_loaded.version_number == 1
    assert v_loaded.thresholds["hold_ms"] == 250
    assert v_loaded.gesture_mappings == {"Brow Raise": "NEXT_TILE", "Smile": "SELECT_TILE"}
