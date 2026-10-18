"""Security, sandboxing, and privacy audit unit tests for MORPH 2.0 (Milestone M5.7)."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from morph.actions.dispatcher import ActionDispatcher
from morph.common.logging import get_logger
from morph.common.security import (
    SecurityViolation,
    audit_zero_video_storage,
    sanitize_export_path,
    validate_action_allowlist,
)
from morph.common.types import ActionType, ConfirmedCommand, RecognitionResult, State
from morph.intent.engine import IntentEngine


def test_network_isolation_audit(monkeypatch):
    """Runtime inference and action dispatch must never initiate network socket connections."""
    calls = []

    def mock_socket_connect(*args, **kwargs):
        calls.append(args)
        raise ConnectionRefusedError(
            "Offline audit: network connections prohibited during runtime!"
        )

    monkeypatch.setattr(socket.socket, "connect", mock_socket_connect)

    # 1. Run IntentEngine
    engine = IntentEngine()
    engine.reset(State.IDLE)
    rec = RecognitionResult(
        frame_id=1,
        t_ns=1000,
        label_scores={"Smile": 0.95},
        best_label="Smile",
        second_label="NONE",
        accepted_candidate_or_none="Smile",
        reject_reason="",
    )
    engine.step(rec, tracking_valid=True, now_ns=1000)

    # 2. Run ActionDispatcher
    dispatcher = ActionDispatcher(mode="LIVE")
    cmd = ConfirmedCommand(
        command_event_uuid="cmd_sec_1",
        frame_id=1,
        confirmed_at_ns=1000,
        gesture_uuid="Smile",
        action_mapping_uuid="NEXT_TILE",
        version_snapshot="v1",
    )
    dispatcher.dispatch(cmd)

    # Zero socket connect attempts
    assert len(calls) == 0


def test_zero_raw_video_storage_audit():
    """Verify repository root contains zero persisted raw video containers or frame dumps."""
    repo_root = Path(__file__).resolve().parents[2]
    report = audit_zero_video_storage(repo_root)

    assert report.passed is True
    assert len(report.prohibited_files) == 0
    assert report.scanned_files_count > 20


def test_video_storage_audit_detects_prohibited_files(tmp_path):
    """Auditor must detect and flag prohibited video containers (.mp4, .avi, etc.)."""
    fake_video = tmp_path / "recording.mp4"
    fake_video.write_bytes(b"dummy video data")

    report = audit_zero_video_storage(tmp_path)
    assert report.passed is False
    assert len(report.prohibited_files) == 1
    assert str(fake_video) in report.prohibited_files[0]


def test_action_allowlist_validation():
    """Only approved AAC communication actions are permitted."""
    for action in ActionType:
        assert validate_action_allowlist(action.value) is True

    # Prohibited dangerous actions
    dangerous = [
        "EXEC_POWERSHELL",
        "DROP_TABLE",
        "FORMAT_DISK",
        "SEND_HTTP_POST",
        "SYSTEM_REBOOT",
    ]
    for bad in dangerous:
        assert validate_action_allowlist(bad) is False


def test_action_dispatcher_sandboxing():
    """ActionDispatcher must fail-closed when encountering unauthorized actions."""
    dispatcher = ActionDispatcher(mode="LIVE")

    cmd_bad = ConfirmedCommand(
        command_event_uuid="cmd_bad",
        frame_id=1,
        confirmed_at_ns=1000,
        gesture_uuid="Smile",
        action_mapping_uuid="EXEC_SHELL_INJECTION",
        version_snapshot="v1",
    )
    res = dispatcher.dispatch(cmd_bad)
    assert res.success is False
    assert res.safe_error_code == "SECURITY_REJECTION_ACTION_NOT_IN_ALLOW_LIST"


def test_export_path_sanitization_valid(tmp_path):
    """Valid filenames resolve strictly inside destination directory."""
    clean = sanitize_export_path(tmp_path, "report_2026.json")
    assert clean.parent == tmp_path.resolve()
    assert clean.name == "report_2026.json"


def test_export_path_sanitization_rejects_traversal(tmp_path):
    """Path traversal sequences must be rejected with SecurityViolation."""
    traversal_attempts = [
        "../escape.json",
        "..\\escape.csv",
        "../../system32/cmd.exe",
        "/etc/shadow",
        "C:\\Windows\\file.json",
        ".",
        "..",
    ]
    for attempt in traversal_attempts:
        with pytest.raises(SecurityViolation):
            sanitize_export_path(tmp_path, attempt)


def test_structured_rotating_logger(tmp_path):
    """Logger must produce structured JSON and enforce 5MB rotation policy."""
    log_dir = tmp_path / "logs"
    logger = get_logger("test_morph_logger", log_dir=log_dir)

    test_msg = "Audit event logged successfully"
    logger.info(test_msg, extra={"metadata": {"subsystem": "security_audit"}})

    log_file = log_dir / "morph.log"
    assert log_file.exists()

    with open(log_file, "r", encoding="utf-8") as f:
        line = f.readline()
        record = json.loads(line)
        assert record["level"] == "INFO"
        assert record["message"] == test_msg
        assert record["metadata"]["subsystem"] == "security_audit"
        assert "timestamp" in record

    # Check handler limits
    handler = logger.handlers[0]
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 3
