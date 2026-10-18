"""Tests for --no-camera CLI launch mode and simulated demonstration operation."""

import sys
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from morph.app import MorphApplication
from morph.common.types import State


def test_no_camera_mode_initialization():
    """Verify that MorphApplication with no_camera=True never creates camera worker."""
    _ = QApplication.instance() or QApplication(sys.argv)

    with (
        patch("morph.app.OpenCVCameraAdapter") as mock_cam,
        patch("morph.app.MediaPipeFaceTracker") as mock_tracker,
    ):
        app = MorphApplication(no_camera=True)

        # Neither camera adapter nor tracker should be instantiated
        mock_cam.assert_not_called()
        mock_tracker.assert_not_called()

        assert app.no_camera is True
        assert app.worker is None
        assert app.window.home_view.lbl_camera.text() == "Camera Sensor: No-Camera Mode (Simulated)"
        assert "NO-CAMERA MODE" in app.window.home_view.toggle_btn.text()
        assert app.window.home_view.toggle_btn.isEnabled() is False

        # Profile management remains functional
        profiles = app.store.list_profiles()
        assert len(profiles) >= 1
        assert app.window.home_view.profile_combo.count() >= 1

        # Attempting to resume in no-camera mode must stay in safe PAUSED state
        app.window.resume_requested.emit()
        assert app.intent_engine.state == State.PAUSED

        # Clean shutdown without error
        app.close()


def test_cli_forwards_no_camera_flag():
    """Verify that python -m morph --no-camera CLI entry point passes no_camera=True."""
    from morph.__main__ import main

    with patch("sys.argv", ["morph", "--no-camera"]), patch("morph.app.run_app") as mock_run_app:
        mock_run_app.return_value = 0
        ret = main()
        assert ret == 0
        mock_run_app.assert_called_once_with(no_camera=True)


def test_cli_normal_launch_passes_no_camera_false():
    """Verify that python -m morph without flags passes no_camera=False."""
    from morph.__main__ import main

    with patch("sys.argv", ["morph"]), patch("morph.app.run_app") as mock_run_app:
        mock_run_app.return_value = 0
        ret = main()
        assert ret == 0
        mock_run_app.assert_called_once_with(no_camera=False)
