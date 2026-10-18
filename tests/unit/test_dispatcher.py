"""Unit tests for ActionDispatcher sandboxing, allow-lists, and deduplication."""

import pytest

from morph.actions.dispatcher import ActionDispatcher, NoOpActionSink
from morph.common.types import ConfirmedCommand


def make_cmd(uuid_str: str, action: str) -> ConfirmedCommand:
    return ConfirmedCommand(
        command_event_uuid=uuid_str,
        frame_id=1,
        confirmed_at_ns=1000,
        gesture_uuid="Brow Raise",
        action_mapping_uuid=action,
        version_snapshot="v1.0",
    )


def test_dispatcher_allow_list_success():
    dispatcher = ActionDispatcher(mode="LIVE")
    executed = []
    dispatcher.register_handler("NEXT_TILE", lambda: executed.append("NEXT_TILE"))

    cmd = make_cmd("cmd_001", "NEXT_TILE")
    res = dispatcher.dispatch(cmd)

    assert res.success is True
    assert res.safe_error_code == ""
    assert executed == ["NEXT_TILE"]


def test_dispatcher_security_rejection_for_unallowed_action():
    dispatcher = ActionDispatcher(mode="LIVE")

    # Prohibited action (e.g. attempting to run shell command)
    prohibited_cmd = make_cmd("cmd_malicious", "RUN_SYSTEM_SHELL")
    res = dispatcher.dispatch(prohibited_cmd)

    assert res.success is False
    assert "SECURITY_REJECTION" in res.safe_error_code


def test_dispatcher_handler_registration_rejects_unallowed_action():
    dispatcher = ActionDispatcher(mode="LIVE")
    with pytest.raises(ValueError, match="not in the action allow-list"):
        dispatcher.register_handler("FORMAT_DISK", lambda: None)


def test_dispatcher_command_deduplication():
    dispatcher = ActionDispatcher(mode="LIVE")
    count = []
    dispatcher.register_handler("SELECT_TILE", lambda: count.append(1))

    cmd = make_cmd("cmd_unique_01", "SELECT_TILE")
    # First dispatch
    res1 = dispatcher.dispatch(cmd)
    assert res1.success is True
    assert len(count) == 1

    # Second dispatch with identical UUID must be blocked
    res2 = dispatcher.dispatch(cmd)
    assert res2.success is False
    assert res2.safe_error_code == "DUPLICATE_COMMAND_UUID_IGNORED"
    assert len(count) == 1  # Handler was not called again!


def test_dispatcher_practice_and_replay_modes_never_trigger_handlers():
    sink = NoOpActionSink()
    dispatcher = ActionDispatcher(mode="PRACTICE", noop_sink=sink)

    real_handler_called = []
    dispatcher.register_handler("SPEAK_TILE", lambda: real_handler_called.append("SPOKEN"))

    cmd = make_cmd("cmd_practice", "SPEAK_TILE")
    res = dispatcher.dispatch(cmd)

    assert res.success is True
    assert len(real_handler_called) == 0  # Real handler was NOT called!
    assert len(sink.recorded_dispatches) == 1  # Routed strictly to NoOp sink!
