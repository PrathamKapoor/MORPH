"""Centralized sandboxed action dispatcher with strict allow-listing."""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Callable

from morph.common.types import ActionResult, ActionType, ConfirmedCommand


class NoOpActionSink:
    """Practice and replay action sink that records hypothetical triggers with zero side effects."""

    def __init__(self):
        self.recorded_dispatches: list[tuple[str, str, int]] = []

    def record(self, cmd: ConfirmedCommand) -> ActionResult:
        now_ns = time.monotonic_ns()
        self.recorded_dispatches.append((cmd.action_mapping_uuid, cmd.command_event_uuid, now_ns))
        return ActionResult(
            command_event_uuid=cmd.command_event_uuid,
            action_name=cmd.action_mapping_uuid,
            dispatched_at_ns=now_ns,
            success=True,
            safe_error_code="",
        )


class ActionDispatcher:
    """The single authorized executor for all internal application side-effects.

    Guarantees:
    1. Only actions in the static ActionType allow-list can be executed.
    2. Prohibits shell commands, file modifications, or arbitrary scripts.
    3. Practice and replay modes strictly route to NoOpActionSink.
    4. Enforces bounded command deduplication by command_event_uuid (capacity limit and retention window).
    """

    ALLOWED_ACTIONS = {action.value for action in ActionType}

    def __init__(
        self,
        mode: str = "LIVE",
        noop_sink: NoOpActionSink | None = None,
        max_capacity: int = 1000,
        retention_sec: float = 60.0,
    ):
        self.mode = mode
        self.noop_sink = noop_sink or NoOpActionSink()
        self._handlers: dict[str, Callable[[], None]] = {}
        self.max_capacity = max_capacity
        self.retention_sec = retention_sec
        self._executed_uuids: OrderedDict[str, int] = OrderedDict()

    def register_handler(self, action_name: str, handler: Callable[[], None]) -> None:
        """Register a callable handler for an allow-listed action."""
        if action_name not in self.ALLOWED_ACTIONS:
            raise ValueError(
                f"Cannot register handler: '{action_name}' is not in the action allow-list!"
            )
        self._handlers[action_name] = handler

    def dispatch(self, cmd: ConfirmedCommand) -> ActionResult:
        """Execute a confirmed command event through the sandbox."""
        now_ns = time.monotonic_ns()

        # Evict entries outside retention window
        cutoff_ns = now_ns - int(self.retention_sec * 1_000_000_000)
        while self._executed_uuids and next(iter(self._executed_uuids.values())) < cutoff_ns:
            self._executed_uuids.popitem(last=False)

        # 1. Deduplication Check
        if cmd.command_event_uuid in self._executed_uuids:
            return ActionResult(
                command_event_uuid=cmd.command_event_uuid,
                action_name=cmd.action_mapping_uuid,
                dispatched_at_ns=now_ns,
                success=False,
                safe_error_code="DUPLICATE_COMMAND_UUID_IGNORED",
            )

        # Evict oldest if capacity is reached
        while len(self._executed_uuids) >= self.max_capacity:
            self._executed_uuids.popitem(last=False)

        self._executed_uuids[cmd.command_event_uuid] = now_ns

        # 2. Strict Allow-List Verification
        action_name = cmd.action_mapping_uuid
        if action_name not in self.ALLOWED_ACTIONS:
            return ActionResult(
                command_event_uuid=cmd.command_event_uuid,
                action_name=action_name,
                dispatched_at_ns=now_ns,
                success=False,
                safe_error_code="SECURITY_REJECTION_ACTION_NOT_IN_ALLOW_LIST",
            )

        # 3. Practice / Replay Mode Sandbox
        if self.mode != "LIVE":
            return self.noop_sink.record(cmd)

        # 4. Live Mode Execution
        handler = self._handlers.get(action_name)
        if handler is not None:
            try:
                handler()
                return ActionResult(
                    command_event_uuid=cmd.command_event_uuid,
                    action_name=action_name,
                    dispatched_at_ns=now_ns,
                    success=True,
                    safe_error_code="",
                )
            except Exception as e:
                return ActionResult(
                    command_event_uuid=cmd.command_event_uuid,
                    action_name=action_name,
                    dispatched_at_ns=now_ns,
                    success=False,
                    safe_error_code=f"HANDLER_EXECUTION_ERROR: {str(e)}",
                )

        return ActionResult(
            command_event_uuid=cmd.command_event_uuid,
            action_name=action_name,
            dispatched_at_ns=now_ns,
            success=False,
            safe_error_code="NO_HANDLER_ATTACHED",
        )
