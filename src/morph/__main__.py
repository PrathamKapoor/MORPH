"""Command-line entry point for python -m morph."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from morph import __version__


def _run_headless_check() -> int:
    """Run non-GUI subsystem self-check and exit with code 0 if healthy."""
    print(f"MORPH {__version__} Headless Subsystem Self-Check:")
    try:
        from morph.capture.tracker import resolve_model_asset_path

        model_p = resolve_model_asset_path()
        if not model_p.exists():
            raise FileNotFoundError(f"Model asset missing at {model_p}")
        print(f"  [OK] Model asset: {model_p} ({model_p.stat().st_size} bytes)")

        import tempfile

        from morph.storage.db import DatabaseManager

        with tempfile.TemporaryDirectory() as td:
            db_file = Path(td) / "headless_check.db"
            db = DatabaseManager(db_file)
            with db.get_connection() as conn:
                cnt = conn.execute(
                    "SELECT count(*) as c FROM sqlite_master WHERE type='table';"
                ).fetchone()["c"]
            print(f"  [OK] SQLite Database engine: {cnt} tables initialized")

        from morph.common.config import RecognitionConfig
        from morph.intent.engine import IntentEngine

        engine = IntentEngine(RecognitionConfig())
        print(f"  [OK] Intent Engine: fail-closed initial state is {engine.state.name}")

        from morph.common.types import ActionType

        print(f"  [OK] Action allowlist: {len(ActionType)} actions active")

        print("MORPH_HEADLESS_CHECK_PASSED")
        return 0
    except Exception as e:
        print(f"MORPH_HEADLESS_CHECK_FAILED: {e}", file=sys.stderr)
        return 1


def main() -> int:
    # On Windows, attach console if running in CLI mode so stdout/stderr display in terminal
    if sys.platform == "win32":
        try:
            import ctypes

            if ctypes.windll.kernel32.AttachConsole(-1):
                if sys.stdout is None or getattr(sys.stdout, "closed", False):
                    sys.stdout = open("CONOUT$", "w", encoding="utf-8")
                if sys.stderr is None or getattr(sys.stderr, "closed", False):
                    sys.stderr = open("CONOUT$", "w", encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="MORPH 2.0: Accessible Facial Gesture AAC System with Deterministic Intention Gating"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"MORPH {__version__}",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run environment health check and exit",
    )
    parser.add_argument(
        "--headless-check",
        action="store_true",
        help="Run headless subsystem integrity test and exit",
    )
    parser.add_argument(
        "--no-camera",
        action="store_true",
        help="Launch UI in simulated/no-camera demonstration mode",
    )
    args = parser.parse_args()

    if args.doctor:
        import subprocess

        return subprocess.call(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", "scripts/doctor.ps1"]
        )

    if args.headless_check:
        return _run_headless_check()

    from morph.app import run_app

    return run_app()


if __name__ == "__main__":
    sys.exit(main())
