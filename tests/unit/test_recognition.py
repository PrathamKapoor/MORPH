"""Unit tests for Condition A and Condition B recognition layers."""

import numpy as np

from morph.common.types import FeaturePacket
from morph.features.normalizer import FeatureExtractor
from morph.recognition.recognizer_a import BaselineRecognizerA
from morph.recognition.recognizer_b import PersonalizedRecognizerB
from tests.fixtures.synthetic_faces import (
    create_synthetic_brow_raise_landmarks,
    create_synthetic_mouth_open_landmarks,
    create_synthetic_neutral_landmarks,
    create_synthetic_smile_landmarks,
)


def test_recognizer_a_fixed_thresholds():
    neutral_lm = create_synthetic_neutral_landmarks()
    eye_dist = float(np.linalg.norm(neutral_lm[263] - neutral_lm[33]))
    extractor = FeatureExtractor(neutral_lm, eye_dist)

    rec_a = BaselineRecognizerA(brow_thresh=0.08, smile_thresh=0.09, mouth_open_thresh=0.08)

    # 1. Brow Raise
    brow_pkt = extractor.extract(create_synthetic_brow_raise_landmarks_packet())
    res_brow = rec_a.predict(brow_pkt)
    assert res_brow.accepted_candidate_or_none == "Brow Raise"
    assert res_brow.best_label == "Brow Raise"

    # 2. Resting neutral (below all thresholds)
    neutral_pkt = extractor.extract(create_synthetic_neutral_landmarks_packet())
    res_neutral = rec_a.predict(neutral_pkt)
    assert res_neutral.accepted_candidate_or_none is None
    assert "BELOW" in res_neutral.reject_reason


def test_recognizer_b_personalized_prototype():
    neutral_lm = create_synthetic_neutral_landmarks()
    eye_dist = float(np.linalg.norm(neutral_lm[263] - neutral_lm[33]))
    extractor = FeatureExtractor(neutral_lm, eye_dist)

    rec_b = PersonalizedRecognizerB(min_similarity=0.65, min_margin=0.15)

    # Train with 5 synthetic samples per gesture
    brow_samples = [
        extractor.extract(create_synthetic_brow_raise_landmarks_packet()).vector for _ in range(5)
    ]
    smile_samples = [
        extractor.extract(create_synthetic_smile_landmarks_packet()).vector for _ in range(5)
    ]
    mouth_samples = [
        extractor.extract(create_synthetic_mouth_open_landmarks_packet()).vector for _ in range(5)
    ]

    rec_b.fit(
        {
            "Brow Raise": brow_samples,
            "Smile / Lip Corner Pull": smile_samples,
            "Chin Raise / Mouth Open": mouth_samples,
        }
    )

    # Test 1: Brow Raise recognition
    test_brow = extractor.extract(create_synthetic_brow_raise_landmarks_packet())
    res_brow = rec_b.predict(test_brow)
    assert res_brow.accepted_candidate_or_none == "Brow Raise"
    assert res_brow.best_label == "Brow Raise"
    assert res_brow.label_scores["Brow Raise"] > 0.90

    # Test 2: Resting neutral rejection
    test_neutral = extractor.extract(create_synthetic_neutral_landmarks_packet())
    res_neutral = rec_b.predict(test_neutral)
    assert res_neutral.accepted_candidate_or_none is None
    assert "RESTING_NEUTRAL" in res_neutral.reject_reason

    # Test 3: Unseen arbitrary movement rejection (random noise vector)
    rng = np.random.default_rng(99)
    noise_vec = rng.normal(0, 1.0, 32)
    noise_pkt = FeaturePacket(
        frame_id=99,
        t_ns=99000,
        feature_schema_version="morph-features-v1.0",
        vector=noise_vec,
        valid=True,
        quality=0.8,
    )
    res_noise = rec_b.predict(noise_pkt)
    # Cosine similarity with specialized prototypes will be low (< 0.65)
    assert res_noise.accepted_candidate_or_none is None
    assert "UNKNOWN_MOVEMENT" in res_noise.reject_reason or "AMBIGUOUS" in res_noise.reject_reason

    # Test 4: Serialization to / from dict round trip
    weights = rec_b.to_dict()
    assert "Brow Raise" in weights
    rec_reloaded = PersonalizedRecognizerB(min_similarity=0.65, min_margin=0.15)
    rec_reloaded.from_dict(weights)
    res_reloaded = rec_reloaded.predict(test_brow)
    assert res_reloaded.accepted_candidate_or_none == "Brow Raise"


def create_synthetic_neutral_landmarks_packet():
    from morph.common.types import LandmarkPacket

    return LandmarkPacket(
        frame_id=1,
        t_ns=1000,
        face_count=1,
        normalized_landmarks=create_synthetic_neutral_landmarks(),
        valid=True,
    )


def create_synthetic_brow_raise_landmarks_packet():
    from morph.common.types import LandmarkPacket

    return LandmarkPacket(
        frame_id=2,
        t_ns=2000,
        face_count=1,
        normalized_landmarks=create_synthetic_brow_raise_landmarks(),
        valid=True,
    )


def create_synthetic_smile_landmarks_packet():
    from morph.common.types import LandmarkPacket

    return LandmarkPacket(
        frame_id=3,
        t_ns=3000,
        face_count=1,
        normalized_landmarks=create_synthetic_smile_landmarks(),
        valid=True,
    )


def create_synthetic_mouth_open_landmarks_packet():
    from morph.common.types import LandmarkPacket

    return LandmarkPacket(
        frame_id=4,
        t_ns=4000,
        face_count=1,
        normalized_landmarks=create_synthetic_mouth_open_landmarks(),
        valid=True,
    )
