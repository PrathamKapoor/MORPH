"""Tests for tracking loss recovery and continuous neutral re-arm safety policy."""

from morph.common.config import RecognitionConfig
from morph.common.types import RecognitionResult, State
from morph.intent.engine import DecisionReason, IntentEngine


def _make_rec(
    frame_id: int,
    t_ns: int,
    candidate: str | None = None,
    best_label: str = "NEUTRAL",
    reject_reason: str = "",
) -> RecognitionResult:
    return RecognitionResult(
        frame_id=frame_id,
        t_ns=t_ns,
        label_scores={candidate: 0.95} if candidate else {},
        best_label=best_label,
        second_label="NONE",
        accepted_candidate_or_none=candidate,
        reject_reason=reject_reason,
    )


def test_face_returning_with_held_gesture_does_not_confirm():
    """If face returns while already holding a command gesture, it must NOT confirm."""
    config = RecognitionConfig(hold_ms=200, rearm_neutral_dwell_ms=200, release_ms=100)
    engine = IntentEngine(config=config)
    engine.reset(State.IDLE)

    t0 = 1_000_000_000

    # 1. Tracking drops
    rec_lost = _make_rec(1, t0, candidate=None, reject_reason="NO_FACE_DETECTED")
    state, cmd, _ = engine.step(rec_lost, tracking_valid=False, now_ns=t0)
    assert state == State.TRACKING_LOST
    assert cmd is None

    # 2. Face reappears holding Brow Raise at t0 + 100ms
    t1 = t0 + 100_000_000
    rec_held = _make_rec(2, t1, candidate="Brow Raise", best_label="Brow Raise")
    state, cmd, trans = engine.step(rec_held, tracking_valid=True, now_ns=t1)

    assert state == State.IDLE
    assert cmd is None
    assert engine._recovered_from_lost is True
    # Rearm dwell start must remain None because the frame was not neutral
    assert engine._rearm_dwell_start_ns is None

    # 3. User continues holding Brow Raise for 400ms (exceeding hold_ms and rearm_dwell)
    for i in range(12):
        t_step = t1 + (i + 1) * 33_000_000
        rec_step = _make_rec(3 + i, t_step, candidate="Brow Raise", best_label="Brow Raise")
        s, c, _ = engine.step(rec_step, tracking_valid=True, now_ns=t_step)
        assert s == State.IDLE
        assert c is None
        assert engine._recovered_from_lost is True
        assert engine._rearm_dwell_start_ns is None


def test_intermittent_twitch_resets_rearm_neutral_dwell():
    """Ambiguity or non-neutral twitches during recovery reset the neutral dwell timer."""
    config = RecognitionConfig(hold_ms=200, rearm_neutral_dwell_ms=200, release_ms=100)
    engine = IntentEngine(config=config)
    engine.reset(State.TRACKING_LOST)

    t0 = 1_000_000_000

    # Step 1: Face reappears neutral at t0 (start neutral dwell)
    rec_n1 = _make_rec(1, t0, candidate=None, best_label="NEUTRAL")
    s, c, _ = engine.step(rec_n1, tracking_valid=True, now_ns=t0)
    assert s == State.IDLE
    assert engine._recovered_from_lost is True
    assert engine._rearm_dwell_start_ns == t0

    # Step 2: 100ms later, face still neutral (halfway through 200ms dwell)
    t1 = t0 + 100_000_000
    rec_n2 = _make_rec(2, t1, candidate=None, best_label="NEUTRAL")
    s, c, _ = engine.step(rec_n2, tracking_valid=True, now_ns=t1)
    assert engine._recovered_from_lost is True
    assert engine._rearm_dwell_start_ns == t0

    # Step 3: Twitch / ambiguous observation at t0 + 150ms
    t2 = t0 + 150_000_000
    rec_amb = _make_rec(
        3, t2, candidate=None, best_label="AMBIGUOUS", reject_reason="AMBIGUOUS_GESTURE"
    )
    s, c, _ = engine.step(rec_amb, tracking_valid=True, now_ns=t2)
    assert engine._recovered_from_lost is True
    # Rearm dwell timer is reset to None
    assert engine._rearm_dwell_start_ns is None
    assert engine.last_decision_reason == DecisionReason.REJECTED_AMBIGUOUS

    # Step 4: Neutral returns at t0 + 200ms (timer restarts from t0 + 200ms)
    t3 = t0 + 200_000_000
    rec_n3 = _make_rec(4, t3, candidate=None, best_label="NEUTRAL")
    s, c, _ = engine.step(rec_n3, tracking_valid=True, now_ns=t3)
    assert engine._recovered_from_lost is True
    assert engine._rearm_dwell_start_ns == t3

    # Step 5: At t0 + 300ms (100ms into new dwell), still locked
    t4 = t0 + 300_000_000
    rec_n4 = _make_rec(5, t4, candidate=None, best_label="NEUTRAL")
    s, c, _ = engine.step(rec_n4, tracking_valid=True, now_ns=t4)
    assert engine._recovered_from_lost is True

    # Step 6: At t0 + 410ms (210ms into new dwell >= 200ms), safe re-arm complete
    t5 = t0 + 410_000_000
    rec_n5 = _make_rec(6, t5, candidate=None, best_label="NEUTRAL")
    s, c, _ = engine.step(rec_n5, tracking_valid=True, now_ns=t5)
    assert engine._recovered_from_lost is False
    assert engine._rearm_dwell_start_ns is None


def test_command_admitted_only_after_successful_neutral_rearm():
    """Once neutral re-arm completes, deliberate commands are cleanly recognized."""
    config = RecognitionConfig(hold_ms=200, rearm_neutral_dwell_ms=200, release_ms=100)
    engine = IntentEngine(config=config)
    engine.reset(State.TRACKING_LOST)

    t0 = 1_000_000_000

    # Frame 1: Tracking restored with neutral
    engine.step(
        _make_rec(1, t0, candidate=None, best_label="NEUTRAL"), tracking_valid=True, now_ns=t0
    )

    # Frame 2: 250ms of continuous neutral (dwell fulfilled)
    t1 = t0 + 250_000_000
    engine.step(
        _make_rec(2, t1, candidate=None, best_label="NEUTRAL"), tracking_valid=True, now_ns=t1
    )
    assert engine._recovered_from_lost is False

    # Frame 3: Deliberate Brow Raise candidate starts
    t2 = t1 + 33_000_000
    s, c, _ = engine.step(
        _make_rec(3, t2, candidate="Brow Raise", best_label="Brow Raise"),
        tracking_valid=True,
        now_ns=t2,
    )
    assert s == State.CANDIDATE
    assert engine.candidate_label == "Brow Raise"

    # Frame 4: Brow Raise sustained past 200ms hold -> Confirms!
    t3 = t2 + 210_000_000
    s, cmd, _ = engine.step(
        _make_rec(4, t3, candidate="Brow Raise", best_label="Brow Raise"),
        tracking_valid=True,
        now_ns=t3,
    )
    assert s == State.CONFIRMED
    assert engine.state == State.COOLDOWN
    assert cmd is not None
    assert cmd.gesture_uuid == "Brow Raise"
    assert cmd.action_mapping_uuid == "NEXT_TILE"
