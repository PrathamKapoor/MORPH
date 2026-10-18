"""Security, action sandboxing, path sanitization, and offline privacy enforcement."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from morph.common.types import ActionType


class SecurityViolation(Exception):
    """Raised when an action, path, or file operation violates sandbox safety boundaries."""


@dataclass(frozen=True)
class StorageAuditReport:
    """Report detailing storage audit results."""

    passed: bool
    scanned_files_count: int
    prohibited_files: list[str]
    details: str


def sanitize_export_path(base_dir: str | Path, filename: str) -> Path:
    """Sanitize and resolve an export path to guarantee it remains strictly within base_dir.

    Prevents directory traversal attacks via '../', absolute paths, or device names.
    """
    base = Path(base_dir).resolve()
    clean_name = os.path.basename(filename.strip())
    if not clean_name or clean_name in (".", ".."):
        raise SecurityViolation(f"Invalid or dangerous filename: '{filename}'")

    if ".." in filename or "/" in filename or "\\" in filename:
        raise SecurityViolation(f"Path traversal characters detected in filename: '{filename}'")

    resolved = (base / clean_name).resolve()
    if not str(resolved).startswith(str(base)):
        raise SecurityViolation(f"Resolved path '{resolved}' escapes base directory '{base}'")

    return resolved


def audit_zero_video_storage(root_path: str | Path) -> StorageAuditReport:
    """Audit project root directory to ensure zero persisted raw video or frame dump files.

    Verifies the zero-video-persistence privacy invariant.
    """
    root = Path(root_path).resolve()
    prohibited_extensions = {
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".h264",
        ".webm",
        ".flv",
        ".raw",
        ".yuv",
    }
    prohibited_found: list[str] = []
    scanned = 0

    ignored_dirs = {
        ".venv",
        ".git",
        "__pycache__",
        "site-packages",
        ".pytest_cache",
        ".ruff_cache",
    }

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignored_dirs]
        for f in filenames:
            scanned += 1
            ext = os.path.splitext(f)[1].lower()
            if ext in prohibited_extensions:
                prohibited_found.append(os.path.join(dirpath, f))

    passed = len(prohibited_found) == 0
    details = (
        f"Clean: 0 video storage files found across {scanned} scanned files."
        if passed
        else f"VIOLATION: Found {len(prohibited_found)} prohibited video files!"
    )
    return StorageAuditReport(
        passed=passed,
        scanned_files_count=scanned,
        prohibited_files=prohibited_found,
        details=details,
    )


def validate_action_allowlist(action_name: str) -> bool:
    """Verify that an action name belongs strictly to the immutable ActionType enum."""
    allowed = {a.value for a in ActionType}
    return action_name in allowed
