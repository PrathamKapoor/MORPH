"""Consented evaluation session management, sequence recording, and ground-truth auditing (M8.2)."""

from __future__ import annotations

import dataclasses
import datetime
import time
import uuid
from typing import Any

from morph.common.types import (
    AnnotationSource,
    EvaluationScenario,
    FeaturePacket,
    GroundTruthEvent,
    GroundTruthLabelType,
)
from morph.storage.db import DatabaseManager


class EvaluationSession:
    """Manages recording of feature sequences and ground truth annotations with informed consent."""

    def __init__(
        self,
        profile_uuid: str,
        consented: bool = False,
        session_uuid: str | None = None,
        db: DatabaseManager | None = None,
        dataset_version: str = "DS-2026.1",
        app_version: str = "2.2.0-rc1",
        model_version: str = "FaceLandmarker-v1",
        test_condition: str = "A_B_C",
        gesture_config: dict[str, Any] | None = None,
        capture_source: str = "PHYSICAL_CAMERA",
        calibration_version: str = "v1.0",
        scenario_id: str = EvaluationScenario.SCEN_01_INTENDED.value,
    ):
        self.profile_uuid = profile_uuid
        self.participant_id = profile_uuid  # Pseudonymous participant identifier (e.g. PART-XXXX)
        self.consented = consented
        self.session_uuid = session_uuid or str(uuid.uuid4())
        self.session_id = self.session_uuid
        self.db = db or DatabaseManager()

        # Metadata specifications (M8.2)
        self.dataset_version = dataset_version
        self.app_version = app_version
        self.model_version = model_version
        self.test_condition = test_condition
        self.gesture_config = gesture_config or {}
        self.capture_source = capture_source
        self.calibration_version = calibration_version
        self.scenario_id = scenario_id
        self.local_monotonic_base_ns = time.perf_counter_ns()
        self.created_at_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Volatile storage
        self.recorded_features: list[FeaturePacket] = []
        self.ground_truth_events: list[GroundTruthEvent] = []
        self.annotation_history: list[dict[str, Any]] = []

    def record_feature(self, packet: FeaturePacket) -> bool:
        """Record a feature packet if informed consent has been granted."""
        if not self.consented:
            return False  # Strict privacy invariant: no consent -> zero storage
        self.recorded_features.append(packet)
        return True

    def add_ground_truth(
        self,
        label: str,
        start_ns: int,
        end_ns: int,
        annotator: str,
        event_uuid: str | None = None,
        label_type: str | GroundTruthLabelType = GroundTruthLabelType.CORRECT_GESTURE,
        notes: str = "",
        annotation_source: str | AnnotationSource = AnnotationSource.TASK_PROMPT,
    ) -> GroundTruthEvent:
        """Add an independently annotated ground truth event."""
        l_type = (
            label_type.value if isinstance(label_type, GroundTruthLabelType) else str(label_type)
        )
        a_src = (
            annotation_source.value
            if isinstance(annotation_source, AnnotationSource)
            else str(annotation_source)
        )

        gt = GroundTruthEvent(
            label=label,
            start_ns=start_ns,
            end_ns=end_ns,
            annotator=annotator,
            session_id=self.session_uuid,
            event_uuid=event_uuid or str(uuid.uuid4()),
            label_type=l_type,
            revision=1,
            notes=notes,
            annotation_source=a_src,
            is_reviewed=False,
        )
        self.ground_truth_events.append(gt)
        return gt

    def update_ground_truth(
        self,
        event_uuid: str,
        label: str | None = None,
        label_type: str | GroundTruthLabelType | None = None,
        start_ns: int | None = None,
        end_ns: int | None = None,
        notes: str | None = None,
        annotator: str | None = None,
    ) -> GroundTruthEvent | None:
        """Review and correct an existing ground-truth annotation, preserving revision history."""
        target_idx = None
        target_event = None
        for idx, evt in enumerate(self.ground_truth_events):
            if evt.event_uuid == event_uuid:
                target_idx = idx
                target_event = evt
                break

        if target_event is None or target_idx is None:
            return None

        # Archive historical revision
        self.annotation_history.append(
            {
                "event_uuid": target_event.event_uuid,
                "revision": target_event.revision,
                "label": target_event.label,
                "label_type": target_event.label_type,
                "start_ns": target_event.start_ns,
                "end_ns": target_event.end_ns,
                "annotator": target_event.annotator,
                "notes": target_event.notes,
                "modified_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        )

        new_label_type = target_event.label_type
        if label_type is not None:
            new_label_type = (
                label_type.value
                if isinstance(label_type, GroundTruthLabelType)
                else str(label_type)
            )

        updated_event = dataclasses.replace(
            target_event,
            label=label if label is not None else target_event.label,
            label_type=new_label_type,
            start_ns=start_ns if start_ns is not None else target_event.start_ns,
            end_ns=end_ns if end_ns is not None else target_event.end_ns,
            notes=notes if notes is not None else target_event.notes,
            annotator=annotator if annotator is not None else target_event.annotator,
            revision=target_event.revision + 1,
            is_reviewed=True,
        )

        self.ground_truth_events[target_idx] = updated_event
        return updated_event

    def delete_ground_truth(self, event_uuid: str) -> bool:
        """Remove an annotation and archive the deletion in history."""
        for idx, evt in enumerate(self.ground_truth_events):
            if evt.event_uuid == event_uuid:
                self.annotation_history.append(
                    {
                        "event_uuid": evt.event_uuid,
                        "revision": evt.revision,
                        "action": "DELETED",
                        "deleted_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    }
                )
                self.ground_truth_events.pop(idx)
                return True
        return False

    def export_session_dict(self) -> dict[str, Any]:
        """Produce structured, pseudonymous dictionary representation for evaluation export."""
        return {
            "session_metadata": {
                "session_uuid": self.session_uuid,
                "participant_id": self.participant_id,
                "dataset_version": self.dataset_version,
                "app_version": self.app_version,
                "model_version": self.model_version,
                "test_condition": self.test_condition,
                "capture_source": self.capture_source,
                "calibration_version": self.calibration_version,
                "scenario_id": self.scenario_id,
                "local_monotonic_base_ns": self.local_monotonic_base_ns,
                "consented": self.consented,
                "created_at_utc": self.created_at_utc,
                "gesture_config": self.gesture_config,
            },
            "ground_truth_events": [
                {
                    "event_uuid": gt.event_uuid,
                    "label": gt.label,
                    "label_type": gt.label_type,
                    "start_ns": gt.start_ns,
                    "end_ns": gt.end_ns,
                    "duration_ms": (gt.end_ns - gt.start_ns) / 1_000_000.0,
                    "annotator": gt.annotator,
                    "annotation_source": gt.annotation_source,
                    "revision": gt.revision,
                    "is_reviewed": gt.is_reviewed,
                    "notes": gt.notes,
                }
                for gt in self.ground_truth_events
            ],
            "annotation_history": self.annotation_history,
            "feature_frame_count": len(self.recorded_features),
        }

    def wipe_session(self) -> bool:
        """Erase volatile memory and hard-delete any persisted database records."""
        self.recorded_features.clear()
        self.ground_truth_events.clear()
        self.annotation_history.clear()

        try:
            with self.db.get_connection() as conn:
                conn.execute(
                    "DELETE FROM evaluation_events WHERE session_uuid = ?;",
                    (self.session_uuid,),
                )
                conn.execute(
                    "DELETE FROM evaluation_sessions WHERE session_uuid = ?;",
                    (self.session_uuid,),
                )
                conn.commit()
            return True
        except Exception:
            return False

    def save_to_db(self) -> bool:
        """Persist session metadata and ground truth events to SQLite."""
        if not self.consented:
            return False

        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO profiles (profile_uuid, name, created_at_utc, updated_at_utc, is_active)
                VALUES (?, ?, ?, ?, 0);
                """,
                (self.profile_uuid, self.profile_uuid, self.created_at_utc, self.created_at_utc),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO evaluation_sessions (session_uuid, profile_uuid, consented, created_at_utc)
                VALUES (?, ?, ?, ?);
                """,
                (self.session_uuid, self.profile_uuid, 1, self.created_at_utc),
            )

            for gt in self.ground_truth_events:
                evt_id = gt.event_uuid or str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT OR REPLACE INTO evaluation_events (event_uuid, session_uuid, label, start_ns, end_ns, event_type)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        evt_id,
                        self.session_uuid,
                        gt.label,
                        gt.start_ns,
                        gt.end_ns,
                        gt.label_type,
                    ),
                )
            conn.commit()
        return True
