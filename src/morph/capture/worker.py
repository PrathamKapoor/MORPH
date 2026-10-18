"""Background capture and landmark processing worker with bounded queues."""

from __future__ import annotations

import collections
import dataclasses
import time

import numpy as np
from PySide6.QtCore import QThread, Signal

from morph.capture.camera import ICameraAdapter, OpenCVCameraAdapter
from morph.capture.tracker import ITrackerAdapter, MediaPipeFaceTracker
from morph.common.config import RecognitionConfig
from morph.common.types import FramePacket, LandmarkPacket, SourceMode, TrackingHealth


class CaptureWorker(QThread):
    """Worker thread running OpenCV camera capture and MediaPipe FaceLandmarker."""

    landmark_ready = Signal(LandmarkPacket)
    frame_ready = Signal(np.ndarray)  # Transient preview image for UI
    health_updated = Signal(TrackingHealth)
    error_occurred = Signal(str)

    def __init__(
        self,
        camera: ICameraAdapter | None = None,
        tracker: ITrackerAdapter | None = None,
        config: RecognitionConfig | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.config = config or RecognitionConfig()
        self.camera = camera or OpenCVCameraAdapter(camera_index=self.config.camera_index)
        self.tracker = tracker  # Lazy initialization if None

        self._running = False
        self._frame_id = 0
        self._last_t_ns = 0

        # Health metrics
        self._dropped_frames = 0
        self._stale_frames = 0
        self._out_of_order_frames = 0
        self._capture_timestamps = collections.deque(maxlen=30)
        self._processed_timestamps = collections.deque(maxlen=30)
        self._last_block_reason = ""
        self._last_face_count = 0
        self._consecutive_read_failures = 0

        # Bounded frame queue: (FramePacket)
        self._frame_queue = collections.deque(maxlen=self.config.bounded_queue_size)

    def stop(self) -> None:
        """Signal the worker thread to stop and wait for completion."""
        self._running = False
        self.wait(1500)
        if self.camera:
            self.camera.release()
        if self.tracker:
            self.tracker.close()

    def run(self) -> None:
        """Main capture loop."""
        self._running = True

        # Ensure tracker is initialized
        if self.tracker is None:
            try:
                self.tracker = MediaPipeFaceTracker()
            except Exception as e:
                self.error_occurred.emit(f"Failed to load tracker model: {e}")
                self._running = False
                return

        # Open camera
        if not self.camera.is_opened():
            opened = self.camera.open()
            if not opened:
                self.error_occurred.emit("Unable to open webcam device.")
                self._last_block_reason = "CAMERA_UNAVAILABLE"
                self._emit_health(0.0, 0.0, False)
                self._running = False
                return

        last_health_emit = time.monotonic_ns()

        while self._running:
            if hasattr(self.camera, "read_timed"):
                success, raw_bgr, t_read_start, t_ns = self.camera.read_timed()
            else:
                t_read_start = time.perf_counter_ns()
                success, raw_bgr, t_ns = self.camera.read()
            now_ns = time.perf_counter_ns()

            if not success or raw_bgr is None:
                self._consecutive_read_failures += 1
                self._last_block_reason = "CAMERA_READ_FAILED"
                self._emit_health(0.0, 0.0, False)
                if self._consecutive_read_failures % 30 == 0:
                    try:
                        self.camera.release()
                        self.camera.open()
                    except Exception:
                        pass
                time.sleep(0.03)
                continue

            self._consecutive_read_failures = 0

            # Check timestamp ordering
            if t_ns <= self._last_t_ns:
                # Out of order or duplicate timestamp; discard
                self._out_of_order_frames += 1
                self._last_block_reason = "OUT_OF_ORDER_TIMESTAMP"
                continue
            self._last_t_ns = t_ns

            # Enforce max frame age
            age_ms = (now_ns - t_ns) / 1_000_000.0
            if age_ms > self.config.max_frame_age_ms:
                self._stale_frames += 1
                self._last_block_reason = (
                    f"FRAME_TOO_OLD ({age_ms:.1f}ms > {self.config.max_frame_age_ms}ms)"
                )
                continue

            self._capture_timestamps.append(t_ns)
            self._frame_id += 1

            # Bounded queue logic: check if queue is full before appending
            if len(self._frame_queue) == self.config.bounded_queue_size:
                self._dropped_frames += 1
                # Drop oldest
                self._frame_queue.popleft()

            t_insert = time.perf_counter_ns()
            packet = FramePacket(
                frame_id=self._frame_id,
                captured_at_monotonic_ns=t_ns,
                bgr_image=raw_bgr,
                source_id="webcam",
                t_read_start_ns=t_read_start,
                t_queue_insert_ns=t_insert,
            )
            self._frame_queue.append(packet)

            # Process the latest available frame from queue
            if self._frame_queue:
                raw_packet = self._frame_queue.pop()
                t_remove = time.perf_counter_ns()
                current_packet = dataclasses.replace(raw_packet, t_queue_remove_ns=t_remove)
                landmark_packet = self.tracker.detect(current_packet)
                self._processed_timestamps.append(time.perf_counter_ns())

                self._last_face_count = landmark_packet.face_count
                if not landmark_packet.valid:
                    self._last_block_reason = landmark_packet.failure_reason

                self.landmark_ready.emit(landmark_packet)
                self.frame_ready.emit(current_packet.bgr_image)

            # Periodic health telemetry emit (~2 Hz)
            if now_ns - last_health_emit > 500_000_000:
                cap_fps = self._calculate_fps(self._capture_timestamps)
                proc_fps = self._calculate_fps(self._processed_timestamps)
                self._emit_health(proc_fps, cap_fps, True)
                last_health_emit = now_ns

            # Polite sleep to match target FPS pacing
            time.sleep(0.005)

        # Cleanup
        if self.camera:
            self.camera.release()
        if self.tracker:
            self.tracker.close()

    def _calculate_fps(self, timestamps: collections.deque[int]) -> float:
        if len(timestamps) < 2:
            return 0.0
        elapsed_sec = (timestamps[-1] - timestamps[0]) / 1_000_000_000.0
        if elapsed_sec <= 0:
            return 0.0
        return (len(timestamps) - 1) / elapsed_sec

    def _emit_health(self, proc_fps: float, cap_fps: float, connected: bool) -> None:
        src_mode = getattr(self.camera, "source_mode", SourceMode.PHYSICAL_CAMERA)
        if not connected or not self.camera or not self.camera.is_opened():
            src_mode = SourceMode.CAMERA_UNAVAILABLE
        health = TrackingHealth(
            processed_fps=proc_fps,
            capture_fps=cap_fps,
            dropped_frames=self._dropped_frames,
            stale_frames=self._stale_frames,
            face_count=self._last_face_count,
            last_block_reason=self._last_block_reason,
            camera_connected=connected,
            out_of_order_frames=self._out_of_order_frames,
            source_mode=src_mode,
        )
        self.health_updated.emit(health)
