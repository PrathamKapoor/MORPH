"""Deterministic unit tests for IntentEngine finite-state machine (Condition C)."""

from morph.common.config import RecognitionConfig
from morph.common.types import RecognitionResult, State
from morph.intent.engine import IntentEngine


def create_rec_result(candidate: str | None, frame_id: int = 1) -> RecognitionResult:
    return RecognitionResult(
        frame_id=frame_id,
        t_ns=frame_id * 33_000_000,
        label_scores={candidate: 0.95} if candidate else {},
        best_label=candidate or "NEUTRAL",
        second_label="NONE",
        accepted_candidate_or_none=candidate,
        reject_reason="" if candidate else "RESTING_NEUTRAL",
    )


def test_intent_engine_idle_to_candidate():
    config = RecognitionConfig(hold_ms=300, release_ms=150, cooldown_ms=300)
    engine = IntentEngine(config=config)
    engine.reset(State.IDLE)

    t0 = 1_000_000_000
    rec = create_rec_result("Brow Raise", frame_id=1)
    state, cmd, trans = engine.step(rec, tracking_valid=True, now_ns=t0, mode="LIVE", paused=False)

    assert state == State.CANDIDATE
    assert cmd is None
    assert len(trans) == 1
    assert trans[0].before == State.IDLE
    assert trans[0].after == State.CANDIDATE
    assert trans[0].label_or_none == "Brow Raise"


def test_intent_engine_hold_duration_and_confirmation():
    config = RecognitionConfig(hold_ms=300, release_ms=150, cooldown_ms=300)
    engine = IntentEngine(config=config)
    engine.reset(State.IDLE)

    t0 = 1_000_000_000
    rec = create_rec_result("Brow Raise", frame_id=1)
    # Step 1: Detect candidate at t0
    state, cmd, _ = engine.step(rec, tracking_valid=True, now_ns=t0)
    assert state == State.CANDIDATE
    assert cmd is None

    # Step 2: 200 ms elapsed (less than 300ms hold) -> should still be CANDIDATE
    t1 = t0 + 200_000_000
    state, cmd, _ = engine.step(rec, tracking_valid=True, now_ns=t1)
    assert state == State.CANDIDATE
    assert cmd is None

    # Step 3: 300 ms elapsed -> exactly hold_ms -> CONFIRMED and transition to COOLDOWN!
    t2 = t0 + 300_000_000
    state, cmd, trans = engine.step(rec, tracking_valid=True, now_ns=t2)
    assert state == State.CONFIRMED
    assert cmd is not None
    assert cmd.gesture_uuid == "Brow Raise"
    assert cmd.action_mapping_uuid == "NEXT_TILE"
    assert engine.state == State.COOLDOWN  # Engine internally advanced to COOLDOWN


def test_intent_engine_candidate_lost_resets_to_idle():
    config = RecognitionConfig(hold_ms=300)
    engine = IntentEngine(config=config)
    engine.reset(State.IDLE)

    t0 = 1_000_000_000
    rec_brow = create_rec_result("Brow Raise", frame_id=1)
    engine.step(rec_brow, tracking_valid=True, now_ns=t0)
    assert engine.state == State.CANDIDATE

    # Movement dropped after 100 ms (aborted/twitch)
    t1 = t0 + 100_000_000
    rec_neutral = create_rec_result(None, frame_id=2)
    state, cmd, trans = engine.step(rec_neutral, tracking_valid=True, now_ns=t1)

    assert state == State.IDLE
    assert cmd is None
    assert any("CANDIDATE_LOST" in tr.reason for tr in trans)


def test_intent_engine_cooldown_and_neutral_release_requirement():
    config = RecognitionConfig(hold_ms=300, release_ms=150, cooldown_ms=300)
    engine = IntentEngine(config=config)
    engine.reset(State.IDLE)

    t0 = 1_000_000_000
    rec_brow = create_rec_result("Brow Raise", frame_id=1)
    engine.step(rec_brow, tracking_valid=True, now_ns=t0)
    # Confirm
    t_confirm = t0 + 300_000_000
    _, cmd, _ = engine.step(rec_brow, tracking_valid=True, now_ns=t_confirm)
    assert cmd is not None
    assert engine.state == State.COOLDOWN

    # Case 1: User continues holding gesture indefinitely for 1 full second
    # Must NOT emit any repeated commands!
    for delta_ms in [100, 200, 300, 500, 1000]:
        t_held = t_confirm + delta_ms * 1_000_000
        state, repeated_cmd, _ = engine.step(rec_brow, tracking_valid=True, now_ns=t_held)
        assert state == State.COOLDOWN
        assert repeated_cmd is None

    # Case 2: User releases to neutral, but for less than release_ms (e.g. 50 ms)
    rec_neutral = create_rec_result(None, frame_id=10)
    t_rel1 = t_confirm + 1050_000_000
    engine.step(rec_neutral, tracking_valid=True, now_ns=t_rel1)
    assert engine.state == State.COOLDOWN

    # Case 3: User releases for full release_ms (150 ms) after total cooldown (300 ms)
    t_rel2 = t_rel1 + 160_000_000
    state, cmd_after, trans = engine.step(rec_neutral, tracking_valid=True, now_ns=t_rel2)
    assert state == State.IDLE
    assert cmd_after is None
    assert any("COOLDOWN_AND_NEUTRAL_RELEASE_SATISFIED" in tr.reason for tr in trans)


def test_intent_engine_suppression_on_pause_and_tracking_lost():
    config = RecognitionConfig(hold_ms=300)
    engine = IntentEngine(config=config)

    # 1. While paused, candidates must never trigger
    rec = create_rec_result("Smile / Lip Corner Pull", frame_id=1)
    t0 = 1_000_000_000
    state, cmd, _ = engine.step(rec, tracking_valid=True, now_ns=t0, paused=True)
    assert state == State.PAUSED
    assert cmd is None

    # 2. Tracking lost (e.g. face occluded or multi-face)
    engine.reset(State.IDLE)
    state_lost, cmd_lost, _ = engine.step(rec, tracking_valid=False, now_ns=t0 + 1000)
    assert state_lost == State.TRACKING_LOST
    assert cmd_lost is None

    # 3. Non-monotonic / backwards timestamp jump
    state_jump, cmd_jump, _ = engine.step(rec, tracking_valid=True, now_ns=t0 - 100_000)
    assert cmd_jump is None
