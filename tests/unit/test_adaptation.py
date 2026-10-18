"""Unit tests for cross-session calibration health, drift detection, and safe adaptation (M5.2 / PRD D03, D04, D06, D07)."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from morph.common.types import LandmarkPacket
from morph.features.drift import (
    CalibrationStatus,
    DriftDetector,
)
from morph.features.normalizer import FeatureExtractor
from morph.storage.db import DatabaseManager
from morph.storage.profiles import ProfileStore
from morph.storage.versions import ProfileVersionManager
from tests.fixtures.synthetic_faces import (
    create_synthetic_brow_raise_landmarks,
    create_synthetic_neutral_landmarks,
)


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_adaptation.db"
        db = DatabaseManager(db_path)
        yield db


def test_drift_detector_stable():
    detector = DriftDetector()
    neutral = create_synthetic_neutral_landmarks()
    interocular = 0.10

    # 10 identical resting frames
    frames = [neutral.copy() for _ in range(10)]
    report = detector.assess_neutral_drift(frames, neutral, interocular)

    assert report.status == CalibrationStatus.STABLE
    assert not report.requires_recalibration
    assert report.baseline_drift < detector.moderate_threshold
    assert "closely matches" in report.explanation


def test_drift_detector_moderate_and_severe():
    detector = DriftDetector(moderate_threshold=0.08, severe_threshold=0.16)
    neutral = create_synthetic_neutral_landmarks()
    interocular = 0.10

    # Shift landmarks along X by 0.010 (displacement = 0.010 / 0.10 = 0.10 -> MODERATE)
    shifted_mod = neutral.copy()
    shifted_mod[:, 0] += 0.010
    report_mod = detector.assess_neutral_drift([shifted_mod] * 5, neutral, interocular)
    assert report_mod.status == CalibrationStatus.MODERATE_DRIFT
    assert not report_mod.requires_recalibration
    assert "Moderate change detected" in report_mod.explanation

    # Shift landmarks along X by 0.020 (displacement = 0.020 / 0.10 = 0.20 -> SEVERE)
    shifted_sev = neutral.copy()
    shifted_sev[:, 0] += 0.020
    report_sev = detector.assess_neutral_drift([shifted_sev] * 5, neutral, interocular)
    assert report_sev.status == CalibrationStatus.SEVERE_DRIFT
    assert report_sev.requires_recalibration
    assert "Significant change detected" in report_sev.explanation


def test_drift_detector_neutral_gesture_overlap():
    detector = DriftDetector()
    neutral = create_synthetic_neutral_landmarks()
    interocular = 0.10
    ext = FeatureExtractor()
    ext.set_neutral_baseline(neutral, interocular)

    brow = create_synthetic_brow_raise_landmarks()
    brow_pkt = ext.extract(
        LandmarkPacket(
            frame_id=1,
            t_ns=0,
            face_count=1,
            normalized_landmarks=brow,
            valid=True,
        )
    )
    brow_proto = brow_pkt.vector

    # If observed resting neutral actually looks like a brow raise
    report = detector.assess_neutral_drift(
        current_neutral_landmarks=[brow] * 5,
        stored_neutral_landmarks=neutral,
        interocular_ref=interocular,
        stored_prototypes={"Brow Raise": brow_proto},
        feature_extractor=ext,
    )

    assert report.status == CalibrationStatus.SEVERE_DRIFT
    assert report.requires_recalibration
    assert "resembles 'Brow Raise'" in report.explanation


def test_drift_detector_non_medical_messaging():
    detector = DriftDetector()
    neutral = create_synthetic_neutral_landmarks()
    shifted = neutral.copy()
    shifted[:, 0] += 0.025
    report = detector.assess_neutral_drift([shifted] * 5, neutral, 0.10)

    # Invariant: Must NOT contain medical or disability diagnostic words
    prohibited_terms = [
        "fatigue",
        "disability",
        "diagnosis",
        "impairment",
        "muscle weakness",
        "disease",
    ]
    explanation_lower = report.explanation.lower()
    recommendation_lower = report.recommendation.lower()
    for term in prohibited_terms:
        assert term not in explanation_lower, (
            f"Prohibited clinical term '{term}' found in explanation"
        )
        assert term not in recommendation_lower, (
            f"Prohibited clinical term '{term}' found in recommendation"
        )


def test_profile_version_manager_lifecycle(temp_db):
    store = ProfileStore(temp_db)
    pid = store.create_profile("Alice")
    mgr = ProfileVersionManager(temp_db)

    neutral = create_synthetic_neutral_landmarks()
    weights_v1 = {"Brow Raise": [0.1] * 32}
    thresh = {"min_similarity": 0.65, "min_margin": 0.15}
    mappings = {"Brow Raise": "NEXT_TILE"}

    # 1. Create version 1 (VALIDATED)
    v1 = mgr.create_version(
        profile_uuid=pid,
        weights=weights_v1,
        thresholds=thresh,
        gesture_mappings=mappings,
        neutral_landmarks=neutral,
        interocular_ref=0.10,
        validation_status="VALIDATED",
        notes="Initial enrollment",
    )
    assert v1.version_number == 1
    assert v1.validation_status == "VALIDATED"

    # Verify active tables were populated
    active_baseline = store.get_neutral_baseline(pid)
    assert active_baseline is not None
    assert np.allclose(active_baseline[0], neutral)

    # 2. Create version 2 (CANDIDATE from recalibration)
    shifted_neutral = neutral.copy()
    shifted_neutral[:, 0] += 0.015
    weights_v2 = {"Brow Raise": [0.2] * 32}
    v2 = mgr.create_version(
        profile_uuid=pid,
        weights=weights_v2,
        thresholds=thresh,
        gesture_mappings=mappings,
        neutral_landmarks=shifted_neutral,
        interocular_ref=0.10,
        validation_status="CANDIDATE",
        notes="Candidate recalibration after camera reposition",
    )
    assert v2.version_number == 2
    assert v2.validation_status == "CANDIDATE"

    # Active baseline must STILL be version 1 (not overwritten by unvalidated candidate!)
    active_baseline_still_v1 = store.get_neutral_baseline(pid)
    assert np.allclose(active_baseline_still_v1[0], neutral)

    # 3. List versions
    versions = mgr.list_versions(pid)
    assert len(versions) == 2

    # 4. Promote candidate to VALIDATED
    promoted_v2 = mgr.promote_candidate(pid, 2)
    assert promoted_v2.validation_status == "VALIDATED"
    # Now active baseline matches version 2
    active_baseline_now_v2 = store.get_neutral_baseline(pid)
    assert np.allclose(active_baseline_now_v2[0], shifted_neutral)

    # 5. Safe rollback to version 1
    rolled_back_v1 = mgr.rollback_to_version(pid, 1)
    assert rolled_back_v1.validation_status == "VALIDATED"
    # Version 2 should now be DEPRECATED
    v2_updated = mgr.get_version_by_number(pid, 2)
    assert v2_updated.validation_status == "DEPRECATED"
    # Active baseline has safely restored version 1
    active_baseline_restored_v1 = store.get_neutral_baseline(pid)
    assert np.allclose(active_baseline_restored_v1[0], neutral)
