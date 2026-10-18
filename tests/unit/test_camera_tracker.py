"""Unit tests for camera adapters and tracker safety invariants."""

import numpy as np

from morph.capture.camera import OpenCVCameraAdapter, SimulatedCameraAdapter
from morph.capture.tracker import SimulatedFaceTracker
from morph.common.types import FramePacket, LandmarkPacket


def test_simulated_camera_adapter():
    frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(3)]
    timestamps = [1000, 2000, 3000]
    cam = SimulatedCameraAdapter(frames=frames, timestamps_ns=timestamps, width=100, height=100)

    assert cam.is_opened() is False
    assert cam.open() is True
    assert cam.is_opened() is True

    ret, frame, t_ns = cam.read()
    assert ret is True
    assert frame is not None
    assert t_ns == 1000

    ret2, frame2, t_ns2 = cam.read()
    assert t_ns2 == 2000

    cam.release()
    assert cam.is_opened() is False


def test_opencv_camera_adapter_graceful_closed():
    cam = OpenCVCameraAdapter(camera_index=999)  # Non-existent camera
    ret, frame, t_ns = cam.read()
    assert ret is False
    assert frame is None
    assert t_ns > 0


def test_tracker_exactly_one_face_rule():
    dummy_packet = FramePacket(
        frame_id=1, captured_at_monotonic_ns=1000, bgr_image=np.zeros((10, 10, 3), dtype=np.uint8)
    )

    # Case 1: Exactly 1 face
    tracker_1 = SimulatedFaceTracker()
    result_1 = tracker_1.detect(dummy_packet)
    assert result_1.valid is True
    assert result_1.face_count == 1
    assert result_1.normalized_landmarks is not None
    assert result_1.normalized_landmarks.shape == (478, 3)

    # Case 2: 0 faces
    res_0 = LandmarkPacket(
        frame_id=1,
        t_ns=1000,
        face_count=0,
        normalized_landmarks=None,
        valid=False,
        failure_reason="NO_FACE_DETECTED",
    )
    tracker_0 = SimulatedFaceTracker(responses=[res_0])
    result_0 = tracker_0.detect(dummy_packet)
    assert result_0.valid is False
    assert result_0.face_count == 0
    assert result_0.failure_reason == "NO_FACE_DETECTED"

    # Case 3: Multiple faces (>1)
    res_multi = LandmarkPacket(
        frame_id=1,
        t_ns=1000,
        face_count=2,
        normalized_landmarks=None,
        valid=False,
        failure_reason="MULTIPLE_FACES_DETECTED",
    )
    tracker_multi = SimulatedFaceTracker(responses=[res_multi])
    result_multi = tracker_multi.detect(dummy_packet)
    assert result_multi.valid is False
    assert result_multi.face_count == 2
    assert "MULTIPLE_FACES" in result_multi.failure_reason


def test_resolve_model_asset_path_dev(monkeypatch):
    """Verify normal development mode model resolution."""
    from morph.capture.tracker import resolve_model_asset_path

    monkeypatch.delattr("sys.frozen", raising=False)
    p = resolve_model_asset_path()
    assert p.name == "face_landmarker.task"
    assert p.exists()


def test_resolve_model_asset_path_custom():
    """Verify explicit custom path is honored unconditionally."""
    from pathlib import Path

    from morph.capture.tracker import resolve_model_asset_path

    custom = Path("some/custom/path.task")
    assert resolve_model_asset_path(custom) == custom


def test_resolve_model_asset_path_frozen_isolated(monkeypatch, tmp_path):
    """Verify frozen environment strictly searches bundle paths and does NOT fall back to repo."""
    import sys

    import pytest

    from morph.capture.tracker import resolve_model_asset_path

    monkeypatch.setattr(sys, "frozen", True, raising=False)

    # Subcase A: Model exists in _internal/models
    fake_exe = tmp_path / "bin" / "morph.exe"
    fake_exe.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    bundled_model = tmp_path / "bin" / "_internal" / "models" / "face_landmarker.task"
    bundled_model.parent.mkdir(parents=True)
    bundled_model.write_bytes(b"dummy_model_bytes")

    resolved = resolve_model_asset_path()
    assert resolved == bundled_model
    assert resolved.read_bytes() == b"dummy_model_bytes"

    # Subcase B: Missing model in frozen bundle raises FileNotFoundError, no fallback
    bundled_model.unlink()
    with pytest.raises(FileNotFoundError, match="Frozen executable bundle missing"):
        resolve_model_asset_path()
