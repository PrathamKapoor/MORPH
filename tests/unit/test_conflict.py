"""Unit tests for gesture conflict and ambiguity detection (M5.1 / PRD A06)."""

import numpy as np
import pytest

from morph.common.types import LandmarkPacket
from morph.features.normalizer import FeatureExtractor
from morph.recognition.conflict import (
    ConflictSeverity,
    GestureConflictDetector,
)
from tests.fixtures.synthetic_faces import (
    create_synthetic_brow_raise_landmarks,
    create_synthetic_mouth_open_landmarks,
    create_synthetic_neutral_landmarks,
    create_synthetic_smile_landmarks,
)


@pytest.fixture
def feature_extractor() -> FeatureExtractor:
    neutral = create_synthetic_neutral_landmarks()
    ext = FeatureExtractor()
    ext.set_neutral_baseline(neutral, 0.1)
    return ext


def test_conflict_detector_invalid_thresholds():
    with pytest.raises(ValueError):
        GestureConflictDetector(strong_threshold=0.6, potential_threshold=0.8)
    with pytest.raises(ValueError):
        GestureConflictDetector(strong_threshold=1.5, potential_threshold=0.5)


def test_insufficient_samples(feature_extractor):
    detector = GestureConflictDetector(min_samples=3)
    # 2 samples instead of 3
    vec = np.zeros(32)
    vec[0] = 1.0
    report = detector.check_conflict("Brow Raise", [vec, vec], {})
    assert report.severity == ConflictSeverity.INSUFFICIENT_DATA
    assert not report.safe_to_activate
    assert "Insufficient valid samples" in report.explanation


def test_nan_and_inf_handling(feature_extractor):
    detector = GestureConflictDetector(min_samples=3)
    vec = np.zeros(32)
    vec[0] = 1.0
    nan_vec = vec.copy()
    nan_vec[5] = np.nan
    inf_vec = vec.copy()
    inf_vec[10] = np.inf

    samples = [vec, nan_vec, inf_vec, vec]  # Only 2 valid finite vectors
    report = detector.check_conflict("Brow Raise", samples, {})
    assert report.severity == ConflictSeverity.INSUFFICIENT_DATA
    assert not report.safe_to_activate


def test_first_gesture_no_conflict(feature_extractor):
    detector = GestureConflictDetector()
    brow_pkt = LandmarkPacket(
        frame_id=1,
        t_ns=1000,
        face_count=1,
        normalized_landmarks=create_synthetic_brow_raise_landmarks(),
        valid=True,
    )
    brow_vec = feature_extractor.extract(brow_pkt).vector
    assert brow_vec is not None

    report = detector.check_conflict("Brow Raise", [brow_vec] * 5, {})
    assert report.severity == ConflictSeverity.NONE
    assert report.safe_to_activate
    assert report.conflicting_label is None


def test_distinct_gestures_no_conflict(feature_extractor):
    detector = GestureConflictDetector()

    brow_vec = feature_extractor.extract(
        LandmarkPacket(
            frame_id=1,
            t_ns=1000,
            face_count=1,
            normalized_landmarks=create_synthetic_brow_raise_landmarks(),
            valid=True,
        )
    ).vector
    smile_vec = feature_extractor.extract(
        LandmarkPacket(
            frame_id=2,
            t_ns=2000,
            face_count=1,
            normalized_landmarks=create_synthetic_smile_landmarks(),
            valid=True,
        )
    ).vector
    mouth_vec = feature_extractor.extract(
        LandmarkPacket(
            frame_id=3,
            t_ns=3000,
            face_count=1,
            normalized_landmarks=create_synthetic_mouth_open_landmarks(),
            valid=True,
        )
    ).vector

    assert brow_vec is not None and smile_vec is not None and mouth_vec is not None

    existing = {
        "Smile": smile_vec / np.linalg.norm(smile_vec),
        "Mouth Open": mouth_vec / np.linalg.norm(mouth_vec),
    }

    report = detector.check_conflict("Brow Raise", [brow_vec] * 5, existing)
    assert report.severity == ConflictSeverity.NONE
    assert report.safe_to_activate
    assert report.similarity < 0.70


def test_identical_or_near_identical_gestures_strong_conflict(feature_extractor):
    detector = GestureConflictDetector(strong_threshold=0.85)

    brow_vec = feature_extractor.extract(
        LandmarkPacket(
            frame_id=1,
            t_ns=1000,
            face_count=1,
            normalized_landmarks=create_synthetic_brow_raise_landmarks(),
            valid=True,
        )
    ).vector
    assert brow_vec is not None

    # Slightly perturbed brow raise (noise std 0.001)
    brow_noisy = brow_vec + np.random.RandomState(42).normal(0, 0.001, size=32)

    existing = {
        "Existing Brow Movement": brow_vec / np.linalg.norm(brow_vec),
    }

    report = detector.check_conflict("New Brow Movement", [brow_noisy] * 5, existing)
    assert report.severity == ConflictSeverity.STRONG
    assert not report.safe_to_activate
    assert report.conflicting_label == "Existing Brow Movement"
    assert report.similarity >= 0.85
    assert "very high feature overlap" in report.explanation


def test_moderate_similarity_potential_conflict():
    detector = GestureConflictDetector(strong_threshold=0.85, potential_threshold=0.70)

    # Synthetic vectors with cosine similarity ~ 0.77
    v1 = np.zeros(32)
    v1[0] = 1.0

    v2 = np.zeros(32)
    v2[0] = 0.77
    v2[1] = np.sqrt(1 - 0.77**2)

    existing = {"Gesture A": v1}
    report = detector.check_conflict("Gesture B", [v2] * 5, existing)

    assert report.severity == ConflictSeverity.POTENTIAL
    assert report.safe_to_activate  # Safe with warning to test in practice mode
    assert report.similarity == pytest.approx(0.77, abs=1e-2)
    assert "moderate similarity" in report.explanation


def test_check_all_pairs():
    detector = GestureConflictDetector()
    v1 = np.zeros(32)
    v1[0] = 1.0
    v2 = np.zeros(32)
    v2[1] = 1.0
    v3 = np.zeros(32)
    v3[0] = 0.95
    v3[1] = np.sqrt(1 - 0.95**2)

    protos = {"G1": v1, "G2": v2, "G3": v3}
    reports = detector.check_all_pairs(protos)
    # Pairs: (G1, G2), (G1, G3), (G2, G3) -> 3 reports
    assert len(reports) == 3
    # G1 and G3 should be strong conflict
    g1_g3 = next(
        r
        for r in reports
        if (r.candidate_label == "G1" and r.conflicting_label == "G3")
        or (r.candidate_label == "G3" and r.conflicting_label == "G1")
    )
    assert g1_g3.severity == ConflictSeverity.STRONG
