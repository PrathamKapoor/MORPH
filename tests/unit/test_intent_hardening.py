"""Unit tests for IntentEngine FSM hardening, transition proofs, and reason codes (M5.3 / PRD B04, B06, B07)."""

from morph.common.config import RecognitionConfig
from morph.common.types import RecognitionResult, State
from morph.intent.engine import DecisionReason, IntentEngine


def make_recognition(
    candidate: str | None = None,
    reject_reason: str = "",
    frame_id: int = 1,
    t_ns: int = 1_000_000,
) -> RecognitionResult:
    return RecognitionResult(
        frame_id=frame_id,
        t_ns=t_ns,
        label_scores={candidate: 0.95} if candidate else {},
        best_label=candidate or "NEUTRAL",
        second_label="NEUTRAL",
        accepted_candidate_or_none=candidate,
        reject_reason=reject_reason,
        recognizer_version="v1",
        profile_version="v1",
    )


def test_valid_intentional_gesture_lifecycle():
    config = RecognitionConfig(hold_ms=250, release_ms=150, cooldown_ms=300)
    engine = IntentEngine(config=config)
    engine.reset(State.IDLE)

    t0 = 10_000_000_000  # 10s baseline

    # Step 1: Detect candidate at t0 (start hold)
    rec = make_recognition("Brow Raise", t_ns=t0)
    state, cmd, trans = engine.step(rec, tracking_valid=True, now_ns=t0, mode="LIVE", paused=False)
    assert state == State.CANDIDATE
    assert cmd is None
    assert engine.last_decision_reason == DecisionReason.REJECTED_INSUFFICIENT_HOLD

    # Step 2: 100ms later (insufficient hold)
    t1 = t0 + 100_000_000
    state, cmd, trans = engine.step(rec, tracking_valid=True, now_ns=t1, mode="LIVE", paused=False)
    assert state == State.CANDIDATE
    assert cmd is None
    assert engine.last_decision_reason == DecisionReason.REJECTED_INSUFFICIENT_HOLD

    # Step 3: 250ms later (hold satisfied!)
    t2 = t0 + 250_000_000
    state, cmd, trans = engine.step(rec, tracking_valid=True, now_ns=t2, mode="LIVE", paused=False)
    assert state == State.CONFIRMED
    assert cmd is not None
    assert cmd.gesture_uuid == "Brow Raise"
    assert cmd.action_mapping_uuid == "NEXT_TILE"
    assert engine.last_decision_reason == DecisionReason.ACCEPTED_GESTURE

    # Step 4: Next frame is in COOLDOWN
    t3 = t0 + 280_000_000
    state, cmd, trans = engine.step(rec, tracking_valid=True, now_ns=t3, mode="LIVE", paused=False)
    assert state == State.COOLDOWN
    assert cmd is None
    assert engine.last_decision_reason == DecisionReason.REJECTED_COOLDOWN


def test_involuntary_short_movement_rejected():
    config = RecognitionConfig(hold_ms=250)
    engine = IntentEngine(config=config)
    engine.reset(State.IDLE)

    t0 = 10_000_000_000
    rec_brow = make_recognition("Brow Raise", t_ns=t0)
    engine.step(rec_brow, tracking_valid=True, now_ns=t0, mode="LIVE", paused=False)

    # User drops back to neutral after only 50ms
    t1 = t0 + 50_000_000
    rec_neutral = make_recognition(None, reject_reason="RESTING_NEUTRAL", t_ns=t1)
    state, cmd, trans = engine.step(
        rec_neutral, tracking_valid=True, now_ns=t1, mode="LIVE", paused=False
    )

    assert state == State.IDLE
    assert cmd is None
    assert engine.last_decision_reason == DecisionReason.REJECTED_LOW_CONFIDENCE


def test_ambiguous_tie_rejected():
    engine = IntentEngine()
    engine.reset(State.IDLE)

    t0 = 10_000_000_000
    rec_brow = make_recognition("Brow Raise", t_ns=t0)
    engine.step(rec_brow, tracking_valid=True, now_ns=t0, mode="LIVE", paused=False)
    assert engine.state == State.CANDIDATE

    # Next frame is ambiguous (separation margin failed)
    t1 = t0 + 33_000_000
    rec_ambig = make_recognition(None, reject_reason="AMBIGUOUS_GESTURE_SEPARATION_MARGIN", t_ns=t1)
    state, cmd, trans = engine.step(
        rec_ambig, tracking_valid=True, now_ns=t1, mode="LIVE", paused=False
    )

    assert state == State.IDLE
    assert cmd is None
    assert engine.last_decision_reason == DecisionReason.REJECTED_AMBIGUOUS


def test_monotonic_clock_regression_safety():
    engine = IntentEngine()
    engine.reset(State.IDLE)

    t0 = 10_000_000_000
    rec = make_recognition("Brow Raise", t_ns=t0)
    engine.step(rec, tracking_valid=True, now_ns=t0, mode="LIVE", paused=False)

    # Clock moves backwards
    t_back = t0 - 50_000_000
    state, cmd, trans = engine.step(
        rec, tracking_valid=True, now_ns=t_back, mode="LIVE", paused=False
    )

    assert cmd is None
    assert engine.last_decision_reason == DecisionReason.REJECTED_CLOCK_REGRESSION


def test_input_frame_gap_clears_candidate():
    engine = IntentEngine(max_gap_ms=500)
    engine.reset(State.IDLE)

    t0 = 10_000_000_000
    rec = make_recognition("Brow Raise", t_ns=t0)
    engine.step(rec, tracking_valid=True, now_ns=t0, mode="LIVE", paused=False)
    assert engine.state == State.CANDIDATE

    # Camera freezes for 600ms
    t_gap = t0 + 600_000_000
    state, cmd, trans = engine.step(
        rec, tracking_valid=True, now_ns=t_gap, mode="LIVE", paused=False
    )

    assert state == State.IDLE
    assert cmd is None
    assert engine.last_decision_reason == DecisionReason.REJECTED_FRAME_GAP


def test_tracking_loss_and_pause_fail_closed():
    engine = IntentEngine()
    engine.reset(State.IDLE)

    t0 = 10_000_000_000
    rec = make_recognition("Brow Raise", t_ns=t0)
    engine.step(rec, tracking_valid=True, now_ns=t0, mode="LIVE", paused=False)
    assert engine.state == State.CANDIDATE

    # Tracking lost mid-hold
    t1 = t0 + 100_000_000
    state, cmd, trans = engine.step(rec, tracking_valid=False, now_ns=t1, mode="LIVE", paused=False)
    assert state == State.TRACKING_LOST
    assert cmd is None
    assert engine.last_decision_reason == DecisionReason.REJECTED_TRACKING_LOSS

    # Pause pressed
    t2 = t0 + 200_000_000
    state, cmd, trans = engine.step(rec, tracking_valid=True, now_ns=t2, mode="LIVE", paused=True)
    assert state == State.PAUSED
    assert cmd is None
    assert engine.last_decision_reason == DecisionReason.REJECTED_PAUSED
