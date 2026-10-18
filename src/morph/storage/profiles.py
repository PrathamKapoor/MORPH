"""High-level user profile and gesture calibration storage for MORPH 2.0."""

from __future__ import annotations

import datetime
import json
import uuid
from typing import Any

import numpy as np

from morph.storage.db import DatabaseManager


class ProfileStore:
    """Manages versioned profiles, neutral baselines, gesture samples, and model snapshots."""

    def __init__(self, db: DatabaseManager | None = None):
        self.db = db or DatabaseManager()

    def create_profile(self, name: str, notes: str = "") -> str:
        """Create a new profile and return its UUID."""
        prof_uuid = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        sql = """
        INSERT INTO profiles (profile_uuid, name, created_at_utc, updated_at_utc, is_active, notes)
        VALUES (?, ?, ?, ?, ?, ?);
        """
        self.db.execute_write(sql, (prof_uuid, name, now, now, 0, notes))
        return prof_uuid

    def get_or_create_default_profile(self) -> str:
        """Return the active or default profile UUID, creating if needed."""
        row = self.db.fetch_one("SELECT profile_uuid FROM profiles WHERE is_active = 1;")
        if row:
            return row["profile_uuid"]

        row = self.db.fetch_one("SELECT profile_uuid FROM profiles LIMIT 1;")
        if row:
            self.set_active_profile(row["profile_uuid"])
            return row["profile_uuid"]

        # Create fresh default
        pid = self.create_profile("Default User Profile", "Auto-created on launch")
        self.set_active_profile(pid)
        return pid

    def set_active_profile(self, profile_uuid: str) -> None:
        """Set one profile as active, deactivating all others."""
        with self.db.get_connection() as conn:
            conn.execute("UPDATE profiles SET is_active = 0;")
            conn.execute(
                "UPDATE profiles SET is_active = 1 WHERE profile_uuid = ?;", (profile_uuid,)
            )
            conn.commit()

    def get_active_profile(self) -> str | None:
        """Return the profile_uuid of the active profile, or None."""
        row = self.db.fetch_one("SELECT profile_uuid FROM profiles WHERE is_active = 1 LIMIT 1;")
        return row["profile_uuid"] if row else None

    def list_profiles(self) -> list[dict[str, Any]]:
        """List all available profiles."""
        return self.db.fetch_all("SELECT * FROM profiles ORDER BY created_at_utc ASC;")

    def save_neutral_baseline(
        self,
        profile_uuid: str,
        median_landmarks: np.ndarray,
        interocular_ref: float,
        created_at_ns: int,
    ) -> str:
        """Store resting neutral baseline landmarks and anatomical scale."""
        neutral_uuid = str(uuid.uuid4())
        blob = median_landmarks.tobytes()

        with self.db.get_connection() as conn:
            # Remove previous baseline for this profile
            conn.execute("DELETE FROM neutral_baselines WHERE profile_uuid = ?;", (profile_uuid,))
            conn.execute(
                """
                INSERT INTO neutral_baselines (neutral_uuid, profile_uuid, landmarks_blob, interocular_ref, created_at_ns)
                VALUES (?, ?, ?, ?, ?);
                """,
                (neutral_uuid, profile_uuid, blob, interocular_ref, created_at_ns),
            )
            conn.commit()
        return neutral_uuid

    def get_neutral_baseline(self, profile_uuid: str) -> tuple[np.ndarray, float] | None:
        """Retrieve stored neutral baseline landmarks and inter-ocular reference."""
        row = self.db.fetch_one(
            "SELECT landmarks_blob, interocular_ref FROM neutral_baselines WHERE profile_uuid = ?;",
            (profile_uuid,),
        )
        if not row:
            return None
        arr = np.frombuffer(row["landmarks_blob"], dtype=np.float64).reshape((478, 3))
        return arr, float(row["interocular_ref"])

    def add_gesture_class(self, profile_uuid: str, name: str, action_type: str) -> str:
        """Register a gesture class under a profile. If it already exists, update action_type."""
        existing = self.db.fetch_one(
            "SELECT gesture_uuid FROM gesture_classes WHERE profile_uuid = ? AND name = ?;",
            (profile_uuid, name),
        )
        if existing:
            self.db.execute_write(
                "UPDATE gesture_classes SET action_type = ? WHERE gesture_uuid = ?;",
                (action_type, existing["gesture_uuid"]),
            )
            return existing["gesture_uuid"]

        gesture_uuid = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        sql = """
        INSERT INTO gesture_classes (gesture_uuid, profile_uuid, name, action_type, created_at_utc)
        VALUES (?, ?, ?, ?, ?);
        """
        self.db.execute_write(sql, (gesture_uuid, profile_uuid, name, action_type, now))
        return gesture_uuid

    def update_gesture_action(self, profile_uuid: str, name: str, action_type: str) -> None:
        """Update action type for a gesture class."""
        self.db.execute_write(
            "UPDATE gesture_classes SET action_type = ? WHERE profile_uuid = ? AND name = ?;",
            (action_type, profile_uuid, name),
        )

    def add_gesture_sample(
        self,
        gesture_uuid: str,
        vector: np.ndarray,
        is_held_out: bool,
        ordinal: int,
        quality: float,
        created_at_ns: int,
    ) -> str:
        """Save a single training or held-out validation sample."""
        sample_uuid = str(uuid.uuid4())
        blob = vector.astype(np.float64).tobytes()
        sql = """
        INSERT INTO gesture_samples (sample_uuid, gesture_uuid, vector_blob, is_held_out, sample_ordinal, quality_score, created_at_ns)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        self.db.execute_write(
            sql,
            (
                sample_uuid,
                gesture_uuid,
                blob,
                1 if is_held_out else 0,
                ordinal,
                quality,
                created_at_ns,
            ),
        )
        return sample_uuid

    def get_gesture_samples(
        self, gesture_uuid: str, held_out: bool | None = None
    ) -> list[tuple[np.ndarray, float]]:
        """Retrieve samples (vector, quality) for a gesture."""
        if held_out is None:
            rows = self.db.fetch_all(
                "SELECT vector_blob, quality_score FROM gesture_samples WHERE gesture_uuid = ? ORDER BY sample_ordinal ASC;",
                (gesture_uuid,),
            )
        else:
            rows = self.db.fetch_all(
                "SELECT vector_blob, quality_score FROM gesture_samples WHERE gesture_uuid = ? AND is_held_out = ? ORDER BY sample_ordinal ASC;",
                (gesture_uuid, 1 if held_out else 0),
            )

        samples = []
        for r in rows:
            vec = np.frombuffer(r["vector_blob"], dtype=np.float64)
            samples.append((vec, float(r["quality_score"])))
        return samples

    def get_profile_gestures(self, profile_uuid: str) -> list[dict[str, Any]]:
        """List all gestures enrolled under a profile."""
        return self.db.fetch_all(
            "SELECT * FROM gesture_classes WHERE profile_uuid = ? ORDER BY created_at_utc ASC;",
            (profile_uuid,),
        )

    get_gesture_classes = get_profile_gestures
    list_gesture_classes = get_profile_gestures

    def delete_gesture_samples(self, gesture_uuid: str) -> None:
        """Clear all samples for a gesture."""
        self.db.execute_write(
            "DELETE FROM gesture_samples WHERE gesture_uuid = ?;", (gesture_uuid,)
        )

    def delete_latest_gesture_sample(self, gesture_uuid: str) -> bool:
        """Delete only the most recently recorded sample for a gesture (precise redo)."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT sample_uuid FROM gesture_samples
                WHERE gesture_uuid = ?
                ORDER BY sample_ordinal DESC, created_at_ns DESC
                LIMIT 1;
                """,
                (gesture_uuid,),
            )
            row = cursor.fetchone()
            if not row:
                return False
            conn.execute(
                "DELETE FROM gesture_samples WHERE sample_uuid = ?;",
                (row["sample_uuid"],),
            )
            conn.commit()
            return True

    def save_model_snapshot(
        self,
        profile_uuid: str,
        model_type: str,
        weights: dict[str, Any],
        thresholds: dict[str, Any],
    ) -> str:
        """Save trained model snapshot JSON."""
        model_uuid = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        weights_str = json.dumps(weights)
        thresh_str = json.dumps(thresholds)

        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM trained_models WHERE profile_uuid = ?;", (profile_uuid,))
            conn.execute(
                """
                INSERT INTO trained_models (model_uuid, profile_uuid, model_type, weights_json, threshold_config_json, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (model_uuid, profile_uuid, model_type, weights_str, thresh_str, now),
            )
            conn.commit()
        return model_uuid

    def get_latest_model_snapshot(self, profile_uuid: str) -> dict[str, Any] | None:
        """Retrieve latest trained model snapshot for a profile."""
        row = self.db.fetch_one(
            "SELECT * FROM trained_models WHERE profile_uuid = ? ORDER BY created_at_utc DESC LIMIT 1;",
            (profile_uuid,),
        )
        if not row:
            return None
        return {
            "model_uuid": row["model_uuid"],
            "model_type": row["model_type"],
            "weights": json.loads(row["weights_json"]),
            "thresholds": json.loads(row["threshold_config_json"]),
            "created_at_utc": row["created_at_utc"],
        }
