"""Camera capture adapters with OpenCV and simulated implementations."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

import cv2
import numpy as np

from morph.common.types import SourceMode


class ICameraAdapter(ABC):
    """Abstract interface for video capture adapters."""

    source_mode: SourceMode = SourceMode.PHYSICAL_CAMERA

    @abstractmethod
    def open(self) -> bool:
        """Open the video capture device."""

    @abstractmethod
    def read(self) -> tuple[bool, np.ndarray | None, int]:
        """Read a frame. Returns (success, bgr_image, monotonic_timestamp_ns)."""

    def read_timed(self) -> tuple[bool, np.ndarray | None, int, int]:
        """Read frame returning (success, bgr_image, t_start_ns, t_done_ns)."""
        t0 = time.perf_counter_ns()
        ret, frame, t1 = self.read()
        return ret, frame, t0, t1

    @abstractmethod
    def release(self) -> None:
        """Release the capture device."""

    @abstractmethod
    def is_opened(self) -> bool:
        """Check if device is currently open."""

    @abstractmethod
    def get_resolution(self) -> tuple[int, int]:
        """Return (width, height) of captured frames."""


class OpenCVCameraAdapter(ICameraAdapter):
    """Windows-optimized OpenCV camera capture using DirectShow."""

    def __init__(
        self,
        camera_index: int = 0,
        preferred_width: int = 640,
        preferred_height: int = 480,
        preferred_fps: int = 30,
    ):
        self.camera_index = camera_index
        self.preferred_width = preferred_width
        self.preferred_height = preferred_height
        self.preferred_fps = preferred_fps
        self._cap: cv2.VideoCapture | None = None
        self._actual_width = 0
        self._actual_height = 0
        self.source_mode = SourceMode.PHYSICAL_CAMERA

    def open(self) -> bool:
        """Open the camera device using cv2.CAP_DSHOW on Windows."""
        try:
            self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                # Fallback to default backend if DSHOW fails
                self._cap = cv2.VideoCapture(self.camera_index)

            if not self._cap.isOpened():
                self.source_mode = SourceMode.CAMERA_UNAVAILABLE
                return False

            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.preferred_width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.preferred_height)
            self._cap.set(cv2.CAP_PROP_FPS, self.preferred_fps)

            self._actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self._actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.source_mode = SourceMode.PHYSICAL_CAMERA
            return True
        except Exception:
            self.source_mode = SourceMode.CAMERA_UNAVAILABLE
            return False

    def read_timed(self) -> tuple[bool, np.ndarray | None, int, int]:
        """Read frame recording blocking camera shutter wait and arrival timestamps."""
        if self._cap is None or not self._cap.isOpened():
            t = time.perf_counter_ns()
            return False, None, t, t

        t_read_start = time.perf_counter_ns()
        ret, frame = self._cap.read()
        t_read_done = time.perf_counter_ns()
        if not ret or frame is None:
            return False, None, t_read_start, t_read_done
        return True, frame, t_read_start, t_read_done

    def read(self) -> tuple[bool, np.ndarray | None, int]:
        """Read frame with precise monotonic arrival timestamp."""
        ret, frame, _, t_done = self.read_timed()
        return ret, frame, t_done

    def release(self) -> None:
        """Safely release camera resource."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def is_opened(self) -> bool:
        """Check if camera is open."""
        return self._cap is not None and self._cap.isOpened()

    def get_resolution(self) -> tuple[int, int]:
        """Return actual resolution."""
        return self._actual_width, self._actual_height


class SimulatedCameraAdapter(ICameraAdapter):
    """Deterministic camera adapter for testing without hardware."""

    def __init__(
        self,
        frames: list[np.ndarray] | None = None,
        timestamps_ns: list[int] | None = None,
        width: int = 640,
        height: int = 480,
    ):
        self.width = width
        self.height = height
        self._is_open = False
        self._idx = 0
        self.source_mode = SourceMode.SYNTHETIC_FIXTURE

        if frames is not None:
            self.frames = frames
        else:
            # Generate 3 dummy BGR frames
            dummy = np.zeros((height, width, 3), dtype=np.uint8)
            self.frames = [dummy.copy(), dummy.copy(), dummy.copy()]

        if timestamps_ns is not None:
            self.timestamps_ns = timestamps_ns
        else:
            now = time.monotonic_ns()
            self.timestamps_ns = [now + i * 33_333_333 for i in range(len(self.frames))]

    def open(self) -> bool:
        self._is_open = True
        self._idx = 0
        return True

    def read(self) -> tuple[bool, np.ndarray | None, int]:
        if not self._is_open or not self.frames:
            return False, None, time.monotonic_ns()

        frame = self.frames[self._idx % len(self.frames)]
        t_ns = self.timestamps_ns[self._idx % len(self.timestamps_ns)]
        self._idx += 1
        return True, frame.copy(), t_ns

    def read_timed(self) -> tuple[bool, np.ndarray | None, int, int]:
        if not self._is_open or not self.frames:
            t = time.perf_counter_ns()
            return False, None, t, t
        t_start = time.perf_counter_ns()
        ret, frame, t_ns = self.read()
        return ret, frame, t_start, t_ns

    def release(self) -> None:
        self._is_open = False

    def is_opened(self) -> bool:
        return self._is_open

    def get_resolution(self) -> tuple[int, int]:
        return self.width, self.height
