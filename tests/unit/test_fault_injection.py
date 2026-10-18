"""Negative tests and fault injection suite for MORPH 2.0 (M4)."""

import socket

from morph.actions.dispatcher import ActionDispatcher
from morph.common.config import RecognitionConfig
from morph.common.types import ConfirmedCommand, RecognitionResult, State
from morph.intent.engine import IntentEngine


def test_fault_injection_tracking_drops_mid_gesture():
    """If camera tracking drops while holding candidate, state machine must abort immediately to TRACKING_LOST and emit 0 commands."""
    config = RecognitionConfig(hold_ms=300)
    engine = IntentEngine(config=config)
    engine.reset(State.IDLE)

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

    # 1. Candidate detected at t0 -> enters CANDIDATE
    state, cmd, _ = engine.step(rec_candidate, tracking_valid=True, now_ns=t0)
    assert state == State.CANDIDATE
    assert cmd is None

    # 2. At t0 + 150ms (halfway through hold), tracking is suddenly LOST (e.g. face turned away or occlusion)
    t1 = t0 + 150_000_000
    rec_lost = RecognitionResult(
        frame_id=2,
        t_ns=t1,
        label_scores={},
        best_label="UNKNOWN",
        second_label="UNKNOWN",
        accepted_candidate_or_none=None,
        reject_reason="NO_FACE_DETECTED",
    )
    state, cmd, trans = engine.step(rec_lost, tracking_valid=False, now_ns=t1)

    assert state == State.TRACKING_LOST
    assert cmd is None
    assert any("TRACKING_INVALID" in tr.reason for tr in trans)


def test_fault_injection_duplicate_commands():
    """Duplicate confirmed command with identical UUID must be blocked from double dispatch."""
    dispatcher = ActionDispatcher(mode="LIVE")
    execution_counter = []
    dispatcher.register_handler("NEXT_TILE", lambda: execution_counter.append(1))

    cmd = ConfirmedCommand(
        command_event_uuid="fixed_uuid_12345",
        frame_id=5,
        confirmed_at_ns=5000,
        gesture_uuid="Brow Raise",
        action_mapping_uuid="NEXT_TILE",
        version_snapshot="v1",
    )

    res1 = dispatcher.dispatch(cmd)
    assert res1.success is True
    assert len(execution_counter) == 1

    # Injected duplicate
    res2 = dispatcher.dispatch(cmd)
    assert res2.success is False
    assert res2.safe_error_code == "DUPLICATE_COMMAND_UUID_IGNORED"
    assert len(execution_counter) == 1


def test_fault_injection_offline_mode_audit(monkeypatch):
    """Runtime inference and intent evaluation must not initiate network socket connections."""
    calls = []

    def mock_socket_connect(*args, **kwargs):
        calls.append(args)
        raise ConnectionRefusedError(
            "Offline audit: network connections prohibited during runtime!"
        )

    monkeypatch.setattr(socket.socket, "connect", mock_socket_connect)

    # Run inference pipeline
    engine = IntentEngine()
    engine.reset(State.IDLE)
    rec = RecognitionResult(
        frame_id=1,
        t_ns=1000,
        label_scores={},
        best_label="NEUTRAL",
        second_label="NONE",
        accepted_candidate_or_none=None,
        reject_reason="",
    )
    state, cmd, _ = engine.step(rec, tracking_valid=True, now_ns=1000)

    # Verify no socket connect was attempted
    assert len(calls) == 0
    assert state == State.IDLE
