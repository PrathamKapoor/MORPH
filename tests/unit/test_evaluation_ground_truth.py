"""Unit tests for real-world evaluation sessions, ground-truth auditing, and admission gating (Milestone M8.2)."""

from __future__ import annotations

import numpy as np

from morph.common.types import (
    FeaturePacket,
    GroundTruthLabelType,
)
from morph.evaluation.session import EvaluationSession
from morph.evaluation.validator import EvaluationSessionValidator
from morph.storage.db import DatabaseManager


def test_pseudonymous_session_and_consent_privacy(tmp_path):
    """Verify session uses pseudonymous participant ID and fail-closed consent invariant."""
    db_file = tmp_path / "test_eval.db"
    db = DatabaseManager(db_path=db_file)

    # Case 1: Unconsented session must reject feature recording
    session_no_consent = EvaluationSession(
        profile_uuid="PART-9F8A12",
        consented=False,
        db=db,
    )
    assert session_no_consent.participant_id.startswith("PART-")
    packet = FeaturePacket(
        frame_id=1,
        t_ns=1_000_000_000,
        feature_schema_version="v1",
        vector=np.zeros(32),
        valid=True,
        quality=1.0,
    )
    assert session_no_consent.record_feature(packet) is False
    assert len(session_no_consent.recorded_features) == 0

    # Case 2: Consented session allows feature recording
    session_consented = EvaluationSession(
        profile_uuid="PART-9F8A12",
        consented=True,
        db=db,
    )
    assert session_consented.record_feature(packet) is True
    assert len(session_consented.recorded_features) == 1


def test_ground_truth_categorical_labeling_and_revisions():
    """Verify ground-truth annotations support categorical types and preserve revision history."""
    session = EvaluationSession(profile_uuid="PART-ABC123", consented=True)

    evt = session.add_ground_truth(
        label="Brow Raise",
        start_ns=1_000_000_000,
        end_ns=1_500_000_000,
        annotator="OPERATOR_1",
        label_type=GroundTruthLabelType.CORRECT_GESTURE,
        notes="Prompted trial 1",
    )
    assert evt.revision == 1
    assert evt.is_reviewed is False
    assert evt.label_type == "CORRECT_GESTURE"
    assert len(session.annotation_history) == 0

    # Review and correct: change category to AMBIGUOUS_OBSERVATION
    updated = session.update_ground_truth(
        event_uuid=evt.event_uuid,
        label_type=GroundTruthLabelType.AMBIGUOUS_OBSERVATION,
        notes="Subject blinked during gesture hold",
        annotator="REVIEWER_2",
    )

    assert updated is not None
    assert updated.revision == 2
    assert updated.is_reviewed is True
    assert updated.label_type == "AMBIGUOUS_OBSERVATION"
    assert len(session.annotation_history) == 1
    assert session.annotation_history[0]["revision"] == 1
    assert session.annotation_history[0]["label_type"] == "CORRECT_GESTURE"

    # Delete annotation
    deleted = session.delete_ground_truth(evt.event_uuid)
    assert deleted is True
    assert len(session.ground_truth_events) == 0
    assert len(session.annotation_history) == 2
    assert session.annotation_history[1]["action"] == "DELETED"


def test_session_validator_admissibility_and_exclusions():
    """Verify EvaluationSessionValidator enforces scientific integrity and admission gates."""
    validator = EvaluationSessionValidator()

    # Gate 1: Unconsented session must be rejected with EXCL_NO_CONSENT
    unconsented_session = EvaluationSession(profile_uuid="PART-001", consented=False)
    res_no_consent = validator.validate_session(unconsented_session)
    assert res_no_consent.is_valid is False
    assert res_no_consent.exclusion_code == "EXCL_NO_CONSENT"

    # Gate 2: Inverted timestamps must be rejected with EXCL_INVALID_TIMESTAMPS
    session_inverted = EvaluationSession(profile_uuid="PART-002", consented=True)
    # Direct append bypassing helper to test corrupted data
    from morph.common.types import GroundTruthEvent

    try:
        corrupted_evt = GroundTruthEvent(
            label="Brow Raise",
            start_ns=2_000_000_000,
            end_ns=1_000_000_000,  # Inverted!
            annotator="TEST",
            session_id=session_inverted.session_uuid,
        )
    except ValueError:
        corrupted_evt = None
    assert corrupted_evt is None  # GroundTruthEvent post_init already prevents inversion!

    # Gate 3: Overlapping mutually exclusive intervals must be rejected with EXCL_LABEL_OVERLAP
    session_overlap = EvaluationSession(profile_uuid="PART-003", consented=True)
    session_overlap.add_ground_truth(
        label="Brow Raise",
        start_ns=1_000_000_000,
        end_ns=2_000_000_000,
        annotator="TEST",
    )
    session_overlap.add_ground_truth(
        label="Smile",
        start_ns=1_800_000_000,  # 200ms overlap!
        end_ns=2_500_000_000,
        annotator="TEST",
    )
    res_overlap = validator.validate_session(session_overlap)
    assert res_overlap.is_valid is False
    assert res_overlap.exclusion_code == "EXCL_LABEL_OVERLAP"

    # Gate 4: Non-enrolled gesture class must be rejected with EXCL_UNKNOWN_GESTURE
    session_unknown = EvaluationSession(profile_uuid="PART-004", consented=True)
    session_unknown.add_ground_truth(
        label="Unregistered Ear Wiggle",
        start_ns=1_000_000_000,
        end_ns=1_500_000_000,
        annotator="TEST",
    )
    res_unknown = validator.validate_session(
        session_unknown, enrolled_gestures={"Brow Raise", "Smile"}
    )
    assert res_unknown.is_valid is False
    assert res_unknown.exclusion_code == "EXCL_UNKNOWN_GESTURE"

    # Gate 5: Train/test data leakage must be rejected with EXCL_TRAIN_TEST_LEAKAGE
    training_sample = np.ones(32, dtype=np.float64) * 0.42
    session_leakage = EvaluationSession(profile_uuid="PART-005", consented=True)
    session_leakage.record_feature(
        FeaturePacket(
            frame_id=1,
            t_ns=1_000_000_000,
            feature_schema_version="v1",
            vector=training_sample.copy(),  # Identical to enrollment!
            valid=True,
            quality=1.0,
        )
    )
    session_leakage.record_feature(
        FeaturePacket(
            frame_id=2,
            t_ns=1_033_333_333,
            feature_schema_version="v1",
            vector=np.zeros(32),
            valid=True,
            quality=1.0,
        )
    )
    res_leakage = validator.validate_session(
        session_leakage, profile_training_samples=[training_sample]
    )
    assert res_leakage.is_valid is False
    assert res_leakage.exclusion_code == "EXCL_TRAIN_TEST_LEAKAGE"

    # Gate 6: Clean, fully compliant session must pass
    clean_session = EvaluationSession(profile_uuid="PART-006", consented=True)
    clean_session.record_feature(
        FeaturePacket(
            frame_id=1,
            t_ns=1_000_000_000,
            feature_schema_version="v1",
            vector=np.zeros(32),
            valid=True,
            quality=1.0,
        )
    )
    clean_session.record_feature(
        FeaturePacket(
            frame_id=2,
            t_ns=2_000_000_000,
            feature_schema_version="v1",
            vector=np.ones(32) * 0.1,
            valid=True,
            quality=1.0,
        )
    )
    clean_session.add_ground_truth(
        label="Brow Raise",
        start_ns=1_200_000_000,
        end_ns=1_700_000_000,
        annotator="TEST",
    )
    res_clean = validator.validate_session(
        clean_session,
        enrolled_gestures={"Brow Raise"},
        profile_training_samples=[np.ones(32) * 0.99],
    )
    assert res_clean.is_valid is True
    assert res_clean.exclusion_code is None
    assert res_clean.total_exposure_sec == 1.0
    assert res_clean.intended_command_count == 1


def test_zero_residue_session_wipe(tmp_path):
    """Verify wipe_session erases volatile memory and database records permanently."""
    db_file = tmp_path / "test_wipe.db"
    db = DatabaseManager(db_path=db_file)

    session = EvaluationSession(profile_uuid="PART-WIPE", consented=True, db=db)
    session.add_ground_truth(
        label="Brow Raise",
        start_ns=1_000_000_000,
        end_ns=1_500_000_000,
        annotator="RESEARCHER",
    )
    saved = session.save_to_db()
    assert saved is True

    # Verify persisted
    with db.get_connection() as conn:
        c1 = conn.execute(
            "SELECT COUNT(*) FROM evaluation_sessions WHERE session_uuid = ?;",
            (session.session_uuid,),
        ).fetchone()[0]
        c2 = conn.execute(
            "SELECT COUNT(*) FROM evaluation_events WHERE session_uuid = ?;",
            (session.session_uuid,),
        ).fetchone()[0]
    assert c1 == 1
    assert c2 == 1

    # Execute wipe
    wiped = session.wipe_session()
    assert wiped is True
    assert len(session.ground_truth_events) == 0
    assert len(session.recorded_features) == 0

    # Verify zero residue in SQLite
    with db.get_connection() as conn:
        c1_after = conn.execute(
            "SELECT COUNT(*) FROM evaluation_sessions WHERE session_uuid = ?;",
            (session.session_uuid,),
        ).fetchone()[0]
        c2_after = conn.execute(
            "SELECT COUNT(*) FROM evaluation_events WHERE session_uuid = ?;",
            (session.session_uuid,),
        ).fetchone()[0]
    assert c1_after == 0
    assert c2_after == 0
