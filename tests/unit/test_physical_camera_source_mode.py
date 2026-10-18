"""Unit tests verifying SourceMode indicators and physical camera degradation (Milestone M7.3)."""

from __future__ import annotations

import numpy as np

from morph.capture.camera import OpenCVCameraAdapter, SimulatedCameraAdapter
from morph.common.types import SourceMode, TrackingHealth
from scripts.validate_physical_camera import validate_physical_camera


def test_source_mode_enum_values():
    """Verify all four canonical source mode strings are defined."""
    assert SourceMode.PHYSICAL_CAMERA.value == "PHYSICAL_CAMERA"
    assert SourceMode.RECORDED_REPLAY.value == "RECORDED_REPLAY"
    assert SourceMode.SYNTHETIC_FIXTURE.value == "SYNTHETIC_FIXTURE"
    assert SourceMode.CAMERA_UNAVAILABLE.value == "CAMERA_UNAVAILABLE"


def test_tracking_health_source_mode_field():
    """Verify TrackingHealth includes source_mode with safe default."""
    health = TrackingHealth(
        processed_fps=30.0,
        capture_fps=30.0,
        dropped_frames=0,
        stale_frames=0,
        face_count=1,
        last_block_reason="",
        camera_connected=True,
        source_mode=SourceMode.PHYSICAL_CAMERA,
    )
    assert health.source_mode == SourceMode.PHYSICAL_CAMERA


def test_simulated_camera_adapter_source_mode():
    """Verify SimulatedCameraAdapter is explicitly tagged as SYNTHETIC_FIXTURE."""
    sim = SimulatedCameraAdapter(frames=[np.zeros((10, 10, 3), dtype=np.uint8)])
    assert sim.source_mode == SourceMode.SYNTHETIC_FIXTURE
    assert sim.open() is True
    assert sim.source_mode == SourceMode.SYNTHETIC_FIXTURE
    sim.release()


def test_opencv_camera_adapter_unavailable_fallback():
    """Verify OpenCVCameraAdapter sets CAMERA_UNAVAILABLE when index is invalid."""
    # Index 99999 is invalid on any hardware
    cam = OpenCVCameraAdapter(camera_index=99999)
    assert cam.open() is False
    assert cam.source_mode == SourceMode.CAMERA_UNAVAILABLE
    cam.release()


def test_validate_physical_camera_report_generation(tmp_path):
    """Verify validate_physical_camera executes and generates structured report."""
    test_md = tmp_path / "PHYSICAL_CAMERA_VALIDATION.md"
    res = validate_physical_camera(output_md_path=test_md)
    assert "source_mode" in res
    assert test_md.exists()
    content = test_md.read_text(encoding="utf-8")
    assert "Physical Camera" in content
    assert res["source_mode"] in content
