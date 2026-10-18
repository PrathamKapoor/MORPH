"""Unit tests for feature normalization, scale-invariance, and quality assessment."""

import numpy as np

from morph.common.types import LandmarkPacket
from morph.features.normalizer import FeatureExtractor
from morph.features.quality import assess_sample_quality
from tests.fixtures.synthetic_faces import (
    create_synthetic_brow_raise_landmarks,
    create_synthetic_neutral_landmarks,
)


def test_feature_extractor_neutral_baseline():
    neutral_lm = create_synthetic_neutral_landmarks()
    eye_dist = float(np.linalg.norm(neutral_lm[263] - neutral_lm[33]))

    extractor = FeatureExtractor()
    extractor.set_neutral_baseline(neutral_lm, eye_dist)

    # When passing neutral landmarks, displacement features (indices 0..11) should be 0.0
    neutral_packet = LandmarkPacket(
        frame_id=1,
        t_ns=1000,
        face_count=1,
        normalized_landmarks=neutral_lm,
        blendshapes={},
        valid=True,
    )

    feat = extractor.extract(neutral_packet)
    assert feat.valid is True
    assert feat.vector.shape == (32,)
    # Displacements relative to self are 0
    assert np.allclose(feat.vector[:12], 0.0, atol=1e-5)


def test_feature_extractor_brow_raise():
    neutral_lm = create_synthetic_neutral_landmarks()
    eye_dist = float(np.linalg.norm(neutral_lm[263] - neutral_lm[33]))

    extractor = FeatureExtractor()
    extractor.set_neutral_baseline(neutral_lm, eye_dist)

    brow_lm = create_synthetic_brow_raise_landmarks()
    packet = LandmarkPacket(
        frame_id=2,
        t_ns=2000,
        face_count=1,
        normalized_landmarks=brow_lm,
        blendshapes={"browInnerUp": 0.85},
        valid=True,
    )

    feat = extractor.extract(packet)
    assert feat.valid is True
    # Brow elevation should be distinctly positive
    assert feat.vector[0] > 0.05
    assert feat.vector[1] > 0.05
    # Blendshape browInnerUp (index 18) should reflect input
    assert feat.vector[18] == 0.85


def test_scale_invariance():
    """Face moved further from camera (scaled by 0.7x) should produce identical normalized displacements."""
    neutral_lm = create_synthetic_neutral_landmarks()
    eye_dist = float(np.linalg.norm(neutral_lm[263] - neutral_lm[33]))

    extractor = FeatureExtractor()
    extractor.set_neutral_baseline(neutral_lm, eye_dist)

    brow_lm = create_synthetic_brow_raise_landmarks()
    feat_normal = extractor.extract(
        LandmarkPacket(
            frame_id=1, t_ns=1000, face_count=1, normalized_landmarks=brow_lm, valid=True
        )
    )

    # Scale face by 0.7 around center (0.5, 0.5)
    brow_scaled = 0.5 + (brow_lm - 0.5) * 0.7
    neutral_scaled = 0.5 + (neutral_lm - 0.5) * 0.7
    scaled_eye_dist = float(np.linalg.norm(neutral_scaled[263] - neutral_scaled[33]))

    extractor_scaled = FeatureExtractor()
    extractor_scaled.set_neutral_baseline(neutral_scaled, scaled_eye_dist)
    feat_scaled = extractor_scaled.extract(
        LandmarkPacket(
            frame_id=2, t_ns=2000, face_count=1, normalized_landmarks=brow_scaled, valid=True
        )
    )

    # Normalized displacements (first 12 features) must be invariant
    assert np.allclose(feat_normal.vector[:12], feat_scaled.vector[:12], atol=1e-4)


def test_sample_quality_assessment():
    neutral_lm = create_synthetic_neutral_landmarks()
    valid_pkt = LandmarkPacket(
        frame_id=1, t_ns=1000, face_count=1, normalized_landmarks=neutral_lm, valid=True
    )
    ok, quality, reason = assess_sample_quality(valid_pkt)
    assert ok is True
    assert quality > 0.5
    assert reason == ""

    # Test boundary clipping (face shifted off screen)
    clipped_lm = neutral_lm.copy()
    clipped_lm[:, 0] += 0.45  # shift out of right edge
    clipped_pkt = LandmarkPacket(
        frame_id=2, t_ns=2000, face_count=1, normalized_landmarks=clipped_lm, valid=True
    )
    ok_clip, _, reason_clip = assess_sample_quality(clipped_pkt)
    assert ok_clip is False
    assert "BOUNDARY" in reason_clip

    # Test steep head tilt
    tilted_lm = neutral_lm.copy()
    tilted_lm[263, 1] += 0.20  # drop right eye
    tilted_pkt = LandmarkPacket(
        frame_id=3, t_ns=3000, face_count=1, normalized_landmarks=tilted_lm, valid=True
    )
    ok_tilt, _, reason_tilt = assess_sample_quality(tilted_pkt)
    assert ok_tilt is False
    assert "TILT" in reason_tilt
