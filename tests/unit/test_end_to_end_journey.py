"""End-to-end integration test verifying complete interactive user journey (Milestone M7.3).

Verifies the 5 essential user stages:
1. Gesture Enrollment (3 movements: Brow Raise, Smile, Mouth Open)
2. Resting Neutral Posture Calibration
3. Hands-Free Communication Board Navigation
4. Offline Windows SAPI TTS Utterance
5. Emergency Fail-Closed Spacebar/Escape Stop
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from morph.actions.dispatcher import ActionDispatcher
from morph.actions.tts import WindowsSapiTTS
from morph.common.config import RecognitionConfig
from morph.common.types import ConfirmedCommand, LandmarkPacket, State
from morph.features.normalizer import FeatureExtractor
from morph.intent.engine import IntentEngine
from morph.recognition.recognizer_b import PersonalizedRecognizerB
from morph.storage.db import DatabaseManager
from morph.storage.profiles import ProfileStore
from tests.fixtures.benchmark_scenarios import BenchmarkScenarioSuite
from tests.fixtures.synthetic_faces import (
    create_synthetic_brow_raise_landmarks,
    create_synthetic_neutral_landmarks,
)


def test_complete_interactive_user_journey():
    """Verify complete 5-stage interactive user journey from calibration to emergency pause."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "morph_e2e.db"
        db = DatabaseManager(db_path)
        store = ProfileStore(db)

        # -------------------------------------------------------------
        # Stage 1: Enrollment of 3 Gestures
        # -------------------------------------------------------------
        profile_uuid = store.create_profile("ALS Participant 01", "Counterbalanced study profile")
        store.set_active_profile(profile_uuid)

        g1_uuid = store.add_gesture_class(profile_uuid, "Brow Raise", "NEXT_TILE")
        g2_uuid = store.add_gesture_class(profile_uuid, "Smile / Lip Corner Pull", "SELECT_TILE")
        g3_uuid = store.add_gesture_class(profile_uuid, "Chin Raise / Mouth Open", "PREVIOUS_TILE")

        suite = BenchmarkScenarioSuite()
        cal_prototypes = suite.get_calibration_prototypes()

        # Enroll 5 samples per gesture
        for vec in cal_prototypes["Brow Raise"]:
            store.add_gesture_sample(
                g1_uuid, vec, is_held_out=False, ordinal=1, quality=1.0, created_at_ns=1000
            )
        for vec in cal_prototypes["Smile / Lip Corner Pull"]:
            store.add_gesture_sample(
                g2_uuid, vec, is_held_out=False, ordinal=1, quality=1.0, created_at_ns=2000
            )
        for vec in cal_prototypes["Chin Raise / Mouth Open"]:
            store.add_gesture_sample(
                g3_uuid, vec, is_held_out=False, ordinal=1, quality=1.0, created_at_ns=3000
            )

        assert len(store.get_gesture_samples(g1_uuid, held_out=False)) == 5
        assert len(store.get_gesture_samples(g2_uuid, held_out=False)) == 5
        assert len(store.get_gesture_samples(g3_uuid, held_out=False)) == 5

        # Fit PersonalizedRecognizerB and persist snapshot
        rec_b = PersonalizedRecognizerB(min_similarity=0.65, min_margin=0.15)
        rec_b.fit(cal_prototypes)

        store.save_model_snapshot(
            profile_uuid,
            model_type="personalized_centroid_v1",
            weights={k: [float(x) for x in v[0]] for k, v in cal_prototypes.items()},
            thresholds={"min_similarity": 0.65, "min_margin": 0.15},
        )
        assert store.get_latest_model_snapshot(profile_uuid) is not None

        # -------------------------------------------------------------
        # Stage 2: Resting Neutral Calibration
        # -------------------------------------------------------------
        neutral_mesh = create_synthetic_neutral_landmarks()
        interocular_scale = 0.30
        store.save_neutral_baseline(
            profile_uuid, neutral_mesh, interocular_scale, created_at_ns=1_000_000_000
        )

        retrieved_neutral = store.get_neutral_baseline(profile_uuid)
        assert retrieved_neutral is not None
        extractor = FeatureExtractor(retrieved_neutral[0], retrieved_neutral[1])

        # -------------------------------------------------------------
        # Stage 3: Communication Board Navigation & Dispatch
        # -------------------------------------------------------------
        # Simulated Communication Board State
        tiles = ["YES", "NO", "PLEASE", "THANK YOU", "HELP", "WATER", "TIRED", "PAIN", "REST"]
        board_state = {"current_index": 0, "selected_phrase": "", "spoken_phrase": ""}

        dispatcher = ActionDispatcher(mode="LIVE")

        def handle_next():
            board_state["current_index"] = (board_state["current_index"] + 1) % len(tiles)

        def handle_prev():
            board_state["current_index"] = (board_state["current_index"] - 1) % len(tiles)

        def handle_select():
            selected = tiles[board_state["current_index"]]
            board_state["selected_phrase"] = selected
            board_state["spoken_phrase"] = selected

        dispatcher.register_handler("NEXT_TILE", handle_next)
        dispatcher.register_handler("PREVIOUS_TILE", handle_prev)
        dispatcher.register_handler("SELECT_TILE", handle_select)

        # Dispatch Sequence: NEXT_TILE -> NEXT_TILE -> PREVIOUS_TILE -> SELECT_TILE
        cmd_next1 = ConfirmedCommand("c1", 10, 1_000_000_000, "Brow Raise", "NEXT_TILE", "v1")
        cmd_next2 = ConfirmedCommand("c2", 20, 2_000_000_000, "Brow Raise", "NEXT_TILE", "v1")
        cmd_prev = ConfirmedCommand("c3", 30, 3_000_000_000, "Mouth Open", "PREVIOUS_TILE", "v1")
        cmd_select = ConfirmedCommand("c4", 40, 4_000_000_000, "Smile", "SELECT_TILE", "v1")

        assert dispatcher.dispatch(cmd_next1).success is True
        assert board_state["current_index"] == 1  # "NO"

        assert dispatcher.dispatch(cmd_next2).success is True
        assert board_state["current_index"] == 2  # "PLEASE"

        assert dispatcher.dispatch(cmd_prev).success is True
        assert board_state["current_index"] == 1  # Back to "NO"

        assert dispatcher.dispatch(cmd_select).success is True
        assert board_state["selected_phrase"] == "NO"
        assert board_state["spoken_phrase"] == "NO"

        # -------------------------------------------------------------
        # Stage 4: SAPI TTS Utterance
        # -------------------------------------------------------------
        tts = WindowsSapiTTS()
        # Speak the chosen board phrase
        tts_result = tts.speak(board_state["spoken_phrase"])
        assert tts_result is True
        tts.close()

        # -------------------------------------------------------------
        # Stage 5: Emergency Spacebar / Esc Stop (Fail-Closed)
        # -------------------------------------------------------------
        engine = IntentEngine(
            config=RecognitionConfig(hold_ms=250, cooldown_ms=300),
            action_mappings={"Brow Raise": "NEXT_TILE"},
        )
        engine.reset(State.IDLE)

        # Feed 1 frame of candidate
        brow_feat = extractor.extract(
            LandmarkPacket(1, 5_000_000_000, 1, create_synthetic_brow_raise_landmarks(), valid=True)
        )
        rec_res = rec_b.predict(brow_feat)
        s, _, _ = engine.step(
            rec_res, tracking_valid=True, now_ns=5_000_000_000, mode="LIVE", paused=False
        )
        assert s == State.CANDIDATE

        # User presses Spacebar / Escape -> emergency pause requested!
        s_paused, cmd_blocked, _ = engine.step(
            rec_res, tracking_valid=True, now_ns=5_300_000_000, mode="LIVE", paused=True
        )
        assert s_paused == State.PAUSED
        assert cmd_blocked is None

        # Verify fail-closed invariant: in PAUSED state, no further dispatches occur
        s_still_paused, cmd_none, _ = engine.step(
            rec_res, tracking_valid=True, now_ns=5_600_000_000, mode="LIVE", paused=True
        )
        assert s_still_paused == State.PAUSED
        assert cmd_none is None
