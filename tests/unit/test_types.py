"""Unit tests for typed contracts and data invariants in morph.common.types."""

import numpy as np
import pytest

from morph.common.types import (
    ActionType,
    FeaturePacket,
    FramePacket,
    GroundTruthEvent,
    LandmarkPacket,
    State,
)


def test_frame_packet_validation():
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    packet = FramePacket(frame_id=1, captured_at_monotonic_ns=1000, bgr_image=img)
    assert packet.frame_id == 1
    assert packet.captured_at_monotonic_ns == 1000

    # Negative frame ID
    with pytest.raises(ValueError):
        FramePacket(frame_id=-1, captured_at_monotonic_ns=1000, bgr_image=img)

    # Negative timestamp
    with pytest.raises(ValueError):
        FramePacket(frame_id=1, captured_at_monotonic_ns=-5, bgr_image=img)

    # Invalid image type
    with pytest.raises(TypeError):
        FramePacket(frame_id=1, captured_at_monotonic_ns=1000, bgr_image="not_an_array")  # type: ignore


def test_landmark_packet_invariants():
    packet = LandmarkPacket(
        frame_id=2,
        t_ns=2000,
        face_count=1,
        normalized_landmarks=np.zeros((478, 3)),
        valid=True,
    )
    assert packet.face_count == 1
    assert packet.valid is True

    # Negative frame_id or t_ns
    with pytest.raises(ValueError):
        LandmarkPacket(frame_id=-1, t_ns=2000, face_count=1, normalized_landmarks=None)
    with pytest.raises(ValueError):
        LandmarkPacket(frame_id=1, t_ns=-2000, face_count=1, normalized_landmarks=None)


def test_feature_packet_nan_inf_rejection():
    # Valid finite vector
    vec_valid = np.ones(32, dtype=np.float64)
    pkt_valid = FeaturePacket(
        frame_id=3,
        t_ns=3000,
        feature_schema_version="morph-features-v1.0",
        vector=vec_valid,
        valid=True,
        quality=0.95,
    )
    assert pkt_valid.valid is True

    # Vector containing NaN must be invalidated
    vec_nan = np.ones(32, dtype=np.float64)
    vec_nan[5] = np.nan
    pkt_nan = FeaturePacket(
        frame_id=4,
        t_ns=4000,
        feature_schema_version="morph-features-v1.0",
        vector=vec_nan,
        valid=True,
        quality=0.95,
    )
    assert pkt_nan.valid is False
    assert "NaN/Inf" in pkt_nan.validity_reason

    # Vector containing Inf must be invalidated
    vec_inf = np.ones(32, dtype=np.float64)
    vec_inf[2] = np.inf
    pkt_inf = FeaturePacket(
        frame_id=5,
        t_ns=5000,
        feature_schema_version="morph-features-v1.0",
        vector=vec_inf,
        valid=True,
        quality=0.95,
    )
    assert pkt_inf.valid is False
    assert "NaN/Inf" in pkt_inf.validity_reason

    # Quality out of bounds
    pkt_bad_q = FeaturePacket(
        frame_id=6,
        t_ns=6000,
        feature_schema_version="morph-features-v1.0",
        vector=vec_valid,
        valid=True,
        quality=1.5,
    )
    assert pkt_bad_q.valid is False
    assert "Quality score out of bounds" in pkt_bad_q.validity_reason


def test_ground_truth_event_timestamps():
    evt = GroundTruthEvent(
        label="BROW_RAISE",
        start_ns=1000,
        end_ns=2000,
        annotator="researcher_1",
        session_id="sess_001",
    )
    assert evt.label == "BROW_RAISE"

    # end_ns before start_ns must raise ValueError
    with pytest.raises(ValueError):
        GroundTruthEvent(
            label="BROW_RAISE",
            start_ns=3000,
            end_ns=2000,
            annotator="researcher_1",
            session_id="sess_001",
        )

    # Negative timestamp
    with pytest.raises(ValueError):
        GroundTruthEvent(
            label="BROW_RAISE",
            start_ns=-100,
            end_ns=2000,
            annotator="researcher_1",
            session_id="sess_001",
        )


def test_state_and_action_enums():
    assert State.PAUSED == "PAUSED"
    assert State.TRACKING_LOST == "TRACKING_LOST"
    assert State.IDLE == "IDLE"
    assert State.CANDIDATE == "CANDIDATE"
    assert State.CONFIRMED == "CONFIRMED"
    assert State.COOLDOWN == "COOLDOWN"

    assert ActionType.NEXT_TILE == "NEXT_TILE"
    assert ActionType.PREVIOUS_TILE == "PREVIOUS_TILE"
    assert ActionType.SELECT_TILE == "SELECT_TILE"
    assert ActionType.SPEAK_TILE == "SPEAK_TILE"
    assert ActionType.BACK == "BACK"
    assert ActionType.PAUSE == "PAUSE"
