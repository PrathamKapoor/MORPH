"""SQLite database manager with migration support for MORPH 2.0."""

from __future__ import annotations

import datetime
import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from morph.storage.schema import MIGRATION_V1, MIGRATION_V2


class DatabaseManager:
    """Manages SQLite connections, transactions, and migrations."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            if getattr(sys, "frozen", False):
                base_dir = (
                    Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
                    / "MORPH"
                    / "data"
                )
            else:
                root = Path(__file__).resolve().parents[3]
                base_dir = root / "data"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = base_dir / "morph.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager yielding a configured sqlite3 connection and guaranteeing close on exit."""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Run schema migrations."""
        with self.get_connection() as conn:
            # Check current version
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at_utc TEXT NOT NULL);"
            )
            cursor = conn.execute("SELECT MAX(version) as current_version FROM schema_version;")
            row = cursor.fetchone()
            current_ver = (
                row["current_version"] if row and row["current_version"] is not None else 0
            )

            if current_ver < 1:
                conn.executescript(MIGRATION_V1)
                now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at_utc) VALUES (?, ?);",
                    (1, now_utc),
                )
                conn.commit()

            if current_ver < 2:
                conn.executescript(MIGRATION_V2)
                now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at_utc) VALUES (?, ?);",
                    (2, now_utc),
                )
                conn.commit()

    def execute_write(self, sql: str, params: tuple = ()) -> int:
        """Execute a write statement inside an atomic transaction."""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount

    def fetch_all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Fetch all rows matching query as list of dicts."""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def fetch_one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        """Fetch one row or return None."""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def close(self) -> None:
        """Close database manager (no-op since connections are context-managed)."""
        pass
