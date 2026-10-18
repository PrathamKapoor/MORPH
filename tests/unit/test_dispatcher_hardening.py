"""Tests for ActionDispatcher sandboxing, deduplication bounds, and IntentEngine unmapped gesture rejection."""

import time

from morph.actions.dispatcher import ActionDispatcher
from morph.common.config import RecognitionConfig
from morph.common.types import ConfirmedCommand, RecognitionResult, State
from morph.intent.engine import IntentEngine


def test_dispatcher_returns_failure_when_no_handler_attached():
    """Actions without registered handlers must fail safely with NO_HANDLER_ATTACHED."""
    dispatcher = ActionDispatcher(mode="LIVE")
    cmd = ConfirmedCommand(
        command_event_uuid="cmd-unhandled-1",
        frame_id=1,
        confirmed_at_ns=1000,
        gesture_uuid="Brow Raise",
        action_mapping_uuid="NEXT_TILE",
        version_snapshot="v1",
    )
    res = dispatcher.dispatch(cmd)
    assert res.success is False
    assert res.safe_error_code == "NO_HANDLER_ATTACHED"


def test_dispatcher_deduplication_bounds_and_capacity_eviction():
    """ActionDispatcher bounded OrderedDict enforces capacity limit and evicts oldest items."""
    executed = []
    dispatcher = ActionDispatcher(mode="LIVE", max_capacity=3, retention_sec=60.0)
    dispatcher.register_handler("NEXT_TILE", lambda: executed.append(1))

    # Dispatch 3 unique commands
    for i in range(1, 4):
        cmd = ConfirmedCommand(
            command_event_uuid=f"uuid-{i}",
            frame_id=i,
            confirmed_at_ns=1000 * i,
            gesture_uuid="Brow Raise",
            action_mapping_uuid="NEXT_TILE",
            version_snapshot="v1",
        )
        res = dispatcher.dispatch(cmd)
        assert res.success is True

    assert len(dispatcher._executed_uuids) == 3
    assert len(executed) == 3

    # Re-dispatching uuid-2 within capacity is rejected as duplicate
    cmd_dup = ConfirmedCommand(
        command_event_uuid="uuid-2",
        frame_id=4,
        confirmed_at_ns=4000,
        gesture_uuid="Brow Raise",
        action_mapping_uuid="NEXT_TILE",
        version_snapshot="v1",
    )
    res_dup = dispatcher.dispatch(cmd_dup)
    assert res_dup.success is False
    assert res_dup.safe_error_code == "DUPLICATE_COMMAND_UUID_IGNORED"
    assert len(executed) == 3

    # Dispatching a 4th unique command evicts oldest (uuid-1)
    cmd_4 = ConfirmedCommand(
        command_event_uuid="uuid-4",
        frame_id=5,
        confirmed_at_ns=5000,
        gesture_uuid="Brow Raise",
        action_mapping_uuid="NEXT_TILE",
        version_snapshot="v1",
    )
    res_4 = dispatcher.dispatch(cmd_4)
    assert res_4.success is True
    assert len(executed) == 4
    assert len(dispatcher._executed_uuids) == 3
    assert "uuid-1" not in dispatcher._executed_uuids
    assert "uuid-4" in dispatcher._executed_uuids


def test_dispatcher_retention_window_eviction():
    """Entries older than retention_sec are evicted during dispatch."""
    executed = []
    dispatcher = ActionDispatcher(mode="LIVE", max_capacity=100, retention_sec=0.05)
    dispatcher.register_handler("NEXT_TILE", lambda: executed.append(1))

    cmd1 = ConfirmedCommand(
        command_event_uuid="uuid-expire-1",
        frame_id=1,
        confirmed_at_ns=1000,
        gesture_uuid="Brow Raise",
        action_mapping_uuid="NEXT_TILE",
        version_snapshot="v1",
    )
    res1 = dispatcher.dispatch(cmd1)
    assert res1.success is True

    # Immediate duplicate is rejected
    res_dup = dispatcher.dispatch(cmd1)
    assert res_dup.success is False
    assert res_dup.safe_error_code == "DUPLICATE_COMMAND_UUID_IGNORED"

    # Sleep past retention window (50ms)
    time.sleep(0.08)

    # Next dispatch evicts expired uuid-expire-1
    cmd2 = ConfirmedCommand(
        command_event_uuid="uuid-expire-2",
        frame_id=2,
        confirmed_at_ns=2000,
        gesture_uuid="Brow Raise",
        action_mapping_uuid="NEXT_TILE",
        version_snapshot="v1",
    )
    res2 = dispatcher.dispatch(cmd2)
    assert res2.success is True
    assert "uuid-expire-1" not in dispatcher._executed_uuids


def test_intent_engine_rejects_unmapped_gesture():
    """Unmapped gestures must be rejected and must never default to NEXT_TILE."""
    engine = IntentEngine(
        config=RecognitionConfig(hold_ms=200, release_ms=100),
        action_mappings={"Brow Raise": "NEXT_TILE"},  # Only Brow Raise is mapped
    )
    engine.reset(State.IDLE)

    t0 = 1_000_000_000
    rec_unmapped = RecognitionResult(
        frame_id=1,
        t_ns=t0,
        label_scores={"Unmapped_Wink": 0.95},
        best_label="Unmapped_Wink",
        second_label="NONE",
        accepted_candidate_or_none="Unmapped_Wink",
        reject_reason="",
    )

    # 1. Candidate starts
    s, c, _ = engine.step(rec_unmapped, tracking_valid=True, now_ns=t0)
    assert s == State.CANDIDATE
    assert c is None

    # 2. Candidate held for 250ms >= hold_ms
    t1 = t0 + 250_000_000
    rec_held = RecognitionResult(
        frame_id=2,
        t_ns=t1,
        label_scores={"Unmapped_Wink": 0.95},
        best_label="Unmapped_Wink",
        second_label="NONE",
        accepted_candidate_or_none="Unmapped_Wink",
        reject_reason="",
    )
    s_end, cmd_end, trans = engine.step(rec_held, tracking_valid=True, now_ns=t1)

    # Must abort to IDLE, emit zero commands, and not default to NEXT_TILE
    assert s_end == State.IDLE
    assert cmd_end is None
    assert any("GESTURE_NOT_MAPPED" in t.reason for t in trans)
