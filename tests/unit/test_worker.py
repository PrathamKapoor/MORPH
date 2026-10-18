"""Unit tests for CaptureWorker bounded queue, stale frame drops, and timestamps."""

import time

import numpy as np
from PySide6.QtCore import QCoreApplication

from morph.capture.camera import SimulatedCameraAdapter
from morph.capture.tracker import SimulatedFaceTracker
from morph.capture.worker import CaptureWorker
from morph.common.config import RecognitionConfig


def test_worker_stale_and_out_of_order_frame_drops():
    _ = QCoreApplication.instance() or QCoreApplication([])

    config = RecognitionConfig(bounded_queue_size=2, max_frame_age_ms=50)

    # Prepare frames:
    # Frame 0: 600ms old -> stale frame (age > 50ms)
    # Frame 1: 700ms old -> out of order frame (earlier than Frame 0)
    # Frame 2: fresh normal frame
    now = time.monotonic_ns()
    frames = [np.zeros((60, 80, 3), dtype=np.uint8) for _ in range(3)]
    timestamps = [
        now - 600_000_000,  # Stale! (600ms old > 50ms)
        now - 700_000_000,  # Out of order! (earlier than Frame 0)
        now + 10_000_000,  # Fresh!
    ]

    camera = SimulatedCameraAdapter(frames=frames, timestamps_ns=timestamps, width=80, height=60)
    tracker = SimulatedFaceTracker()

    worker = CaptureWorker(camera=camera, tracker=tracker, config=config)

    received_landmarks = []
    worker.landmark_ready.connect(lambda lm: received_landmarks.append(lm))

    worker.start()
    time.sleep(0.2)
    worker.stop()

    # Out of order and stale frames must be properly counted
    assert worker._stale_frames >= 1
    assert worker._out_of_order_frames >= 1
