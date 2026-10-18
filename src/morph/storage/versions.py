"""Profile versioning, candidate promotion, and safe rollback manager (PRD D07 / M5.2).

Ensures all recalibrations produce immutable, versioned snapshots in SQLite,
preventing silent model replacement and supporting instant rollback to prior validated states.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np

from morph.storage.db import DatabaseManager


@dataclass(frozen=True)
class ProfileVersion:
    """Immutable snapshot of a profile's calibration, recognizer weights, and mappings."""

    version_uuid: str
    profile_uuid: str
    version_number: int
    feature_schema_version: str
    weights: dict[str, Any]
    thresholds: dict[str, Any]
    gesture_mappings: dict[str, str]
    neutral_landmarks: np.ndarray
    interocular_ref: float
    validation_status: str  # 'VALIDATED', 'CANDIDATE', 'DEPRECATED'
    created_at_utc: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_uuid": self.version_uuid,
            "profile_uuid": self.profile_uuid,
            "version_number": self.version_number,
            "feature_schema_version": self.feature_schema_version,
            "thresholds": self.thresholds,
            "gesture_mappings": self.gesture_mappings,
            "interocular_ref": round(self.interocular_ref, 4),
            "validation_status": self.validation_status,
            "created_at_utc": self.created_at_utc,
            "notes": self.notes,
        }


class ProfileVersionManager:
    """Manages profile version history, candidate evaluations, and safe rollbacks."""

    def __init__(self, db: DatabaseManager | None = None):
        self.db = db or DatabaseManager()

    def create_version(
        self,
        profile_uuid: str,
        weights: dict[str, Any],
        thresholds: dict[str, Any],
        gesture_mappings: dict[str, str],
        neutral_landmarks: np.ndarray,
        interocular_ref: float,
        validation_status: str = "VALIDATED",
        notes: str = "",
        feature_schema_version: str = "morph-features-v1.0",
    ) -> ProfileVersion:
        """Create a new immutable profile version snapshot."""
        if neutral_landmarks.shape != (478, 3) or not np.all(np.isfinite(neutral_landmarks)):
            raise ValueError(f"Invalid neutral landmarks shape {neutral_landmarks.shape}")
        if interocular_ref <= 1e-4:
            raise ValueError(f"Invalid interocular reference scale: {interocular_ref}")
        if validation_status not in ("VALIDATED", "CANDIDATE", "DEPRECATED"):
            raise ValueError(f"Unknown validation status: {validation_status}")

        version_uuid = str(uuid.uuid4())
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        blob = neutral_landmarks.astype(np.float64).tobytes()
        weights_json = json.dumps(weights)
        thresh_json = json.dumps(thresholds)
        mappings_json = json.dumps(gesture_mappings)

        next_v = 1
        for attempt in range(5):
            try:
                with self.db.get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT COALESCE(MAX(version_number), 0) + 1 as next_v FROM profile_versions WHERE profile_uuid = ?;",
                        (profile_uuid,),
                    )
                    row = cursor.fetchone()
                    next_v = row["next_v"]

                    conn.execute(
                        """
                        INSERT INTO profile_versions (
                            version_uuid, profile_uuid, version_number, feature_schema_version,
                            weights_json, threshold_config_json, gesture_mappings_json,
                            neutral_landmarks_blob, interocular_ref, validation_status,
                            created_at_utc, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            version_uuid,
                            profile_uuid,
                            next_v,
                            feature_schema_version,
                            weights_json,
                            thresh_json,
                            mappings_json,
                            blob,
                            float(interocular_ref),
                            validation_status,
                            now_utc,
                            notes,
                        ),
                    )

                    # If promoted immediately as VALIDATED, sync to active tables
                    if validation_status == "VALIDATED":
                        self._sync_active_tables(
                            conn,
                            profile_uuid,
                            weights_json,
                            thresh_json,
                            mappings_json,
                            blob,
                            interocular_ref,
                        )

                    conn.commit()
                    break
            except sqlite3.IntegrityError:
                if attempt == 4:
                    raise
                time.sleep(0.01 * (attempt + 1))

        return ProfileVersion(
            version_uuid=version_uuid,
            profile_uuid=profile_uuid,
            version_number=next_v,
            feature_schema_version=feature_schema_version,
            weights=weights,
            thresholds=thresholds,
            gesture_mappings=gesture_mappings,
            neutral_landmarks=neutral_landmarks.copy(),
            interocular_ref=float(interocular_ref),
            validation_status=validation_status,
            created_at_utc=now_utc,
            notes=notes,
        )

    def _sync_active_tables(
        self,
        conn: Any,
        profile_uuid: str,
        weights_json: str,
        threshold_config_json: str,
        gesture_mappings_json: str,
        neutral_blob: bytes,
        interocular_ref: float,
    ) -> None:
        """Sync a validated version snapshot to active runtime tables inside transaction."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        now_ns = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1e9)

        # 1. Sync neutral baseline
        conn.execute("DELETE FROM neutral_baselines WHERE profile_uuid = ?;", (profile_uuid,))
        conn.execute(
            """
            INSERT INTO neutral_baselines (neutral_uuid, profile_uuid, landmarks_blob, interocular_ref, created_at_ns)
            VALUES (?, ?, ?, ?, ?);
            """,
            (str(uuid.uuid4()), profile_uuid, neutral_blob, interocular_ref, now_ns),
        )

        # 2. Sync trained models
        conn.execute("DELETE FROM trained_models WHERE profile_uuid = ?;", (profile_uuid,))
        conn.execute(
            """
            INSERT INTO trained_models (model_uuid, profile_uuid, model_type, weights_json, threshold_config_json, created_at_utc)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                str(uuid.uuid4()),
                profile_uuid,
                "personalized_b",
                weights_json,
                threshold_config_json,
                now,
            ),
        )

        # 3. Sync gesture mappings
        mappings = json.loads(gesture_mappings_json)
        for g_name, act_type in mappings.items():
            existing = conn.execute(
                "SELECT gesture_uuid FROM gesture_classes WHERE profile_uuid = ? AND name = ?;",
                (profile_uuid, g_name),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE gesture_classes SET action_type = ? WHERE gesture_uuid = ?;",
                    (act_type, existing["gesture_uuid"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO gesture_classes (gesture_uuid, profile_uuid, name, action_type, created_at_utc)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (str(uuid.uuid4()), profile_uuid, g_name, act_type, now),
                )

    def list_versions(self, profile_uuid: str) -> list[ProfileVersion]:
        """Return all historical versions for a profile in ascending order."""
        rows = self.db.fetch_all(
            "SELECT * FROM profile_versions WHERE profile_uuid = ? ORDER BY version_number ASC;",
            (profile_uuid,),
        )
        versions: list[ProfileVersion] = []
        for r in rows:
            arr = np.frombuffer(r["neutral_landmarks_blob"], dtype=np.float64).reshape((478, 3))
            versions.append(
                ProfileVersion(
                    version_uuid=r["version_uuid"],
                    profile_uuid=r["profile_uuid"],
                    version_number=r["version_number"],
                    feature_schema_version=r["feature_schema_version"],
                    weights=json.loads(r["weights_json"]),
                    thresholds=json.loads(r["threshold_config_json"]),
                    gesture_mappings=json.loads(r["gesture_mappings_json"]),
                    neutral_landmarks=arr,
                    interocular_ref=float(r["interocular_ref"]),
                    validation_status=r["validation_status"],
                    created_at_utc=r["created_at_utc"],
                    notes=r["notes"] or "",
                )
            )
        return versions

    def get_version_by_number(
        self, profile_uuid: str, version_number: int
    ) -> ProfileVersion | None:
        """Fetch a specific version by its version number."""
        row = self.db.fetch_one(
            "SELECT * FROM profile_versions WHERE profile_uuid = ? AND version_number = ?;",
            (profile_uuid, version_number),
        )
        if not row:
            return None
        arr = np.frombuffer(row["neutral_landmarks_blob"], dtype=np.float64).reshape((478, 3))
        return ProfileVersion(
            version_uuid=row["version_uuid"],
            profile_uuid=row["profile_uuid"],
            version_number=row["version_number"],
            feature_schema_version=row["feature_schema_version"],
            weights=json.loads(row["weights_json"]),
            thresholds=json.loads(row["threshold_config_json"]),
            gesture_mappings=json.loads(row["gesture_mappings_json"]),
            neutral_landmarks=arr,
            interocular_ref=float(row["interocular_ref"]),
            validation_status=row["validation_status"],
            created_at_utc=row["created_at_utc"],
            notes=row["notes"] or "",
        )

    def rollback_to_version(self, profile_uuid: str, version_number: int) -> ProfileVersion:
        """Atomically revert active profile configuration to a prior validated version."""
        target = self.get_version_by_number(profile_uuid, version_number)
        if target is None:
            raise KeyError(f"Profile {profile_uuid} has no version {version_number}")

        with self.db.get_connection() as conn:
            # Mark newer versions as DEPRECATED
            conn.execute(
                "UPDATE profile_versions SET validation_status = 'DEPRECATED' WHERE profile_uuid = ? AND version_number > ?;",
                (profile_uuid, version_number),
            )
            # Mark target version as VALIDATED
            conn.execute(
                "UPDATE profile_versions SET validation_status = 'VALIDATED' WHERE profile_uuid = ? AND version_number = ?;",
                (profile_uuid, version_number),
            )

            # Sync active runtime tables
            weights_json = json.dumps(target.weights)
            thresh_json = json.dumps(target.thresholds)
            mappings_json = json.dumps(target.gesture_mappings)
            neutral_blob = target.neutral_landmarks.astype(np.float64).tobytes()

            self._sync_active_tables(
                conn,
                profile_uuid,
                weights_json,
                thresh_json,
                mappings_json,
                neutral_blob,
                target.interocular_ref,
            )
            conn.commit()

        return self.get_version_by_number(profile_uuid, version_number)  # type: ignore

    def promote_candidate(self, profile_uuid: str, version_number: int) -> ProfileVersion:
        """Promote a candidate recalibration version to VALIDATED active status."""
        return self.rollback_to_version(profile_uuid, version_number)
