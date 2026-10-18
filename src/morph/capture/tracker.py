"""MediaPipe Face Landmarker adapter and tracking validation."""

from __future__ import annotations

import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from morph.common.types import FramePacket, LandmarkPacket


def resolve_model_asset_path(model_asset_path: str | Path | None = None) -> Path:
    """Resolve MediaPipe face_landmarker.task model path across dev, frozen, and test environments.

    In frozen PyInstaller bundles (sys.frozen == True), model resolution is strictly isolated to the
    bundle paths (sys._MEIPASS or executable directory) and will NOT fall back to development paths.
    """
    if model_asset_path is not None:
        return Path(model_asset_path)

    # 1. PyInstaller frozen bundles
    if getattr(sys, "frozen", False):
        frozen_candidates: list[Path] = []
        if hasattr(sys, "_MEIPASS"):
            frozen_candidates.append(Path(sys._MEIPASS) / "models" / "face_landmarker.task")
        exe_dir = Path(sys.executable).parent
        frozen_candidates.append(exe_dir / "_internal" / "models" / "face_landmarker.task")
        frozen_candidates.append(exe_dir / "models" / "face_landmarker.task")

        for c in frozen_candidates:
            if c.exists():
                return c

        raise FileNotFoundError(
            f"Frozen executable bundle missing MediaPipe model asset. Checked paths: "
            f"{[str(p) for p in frozen_candidates]}. "
            "Ensure models/face_landmarker.task is bundled by PyInstaller."
        )

    # 2. In development / test environment:
    candidates: list[Path] = [
        # Repo root relative to source file
        Path(__file__).resolve().parents[3] / "models" / "face_landmarker.task",
        # Current working directory
        Path("models/face_landmarker.task").resolve(),
    ]

    for c in candidates:
        if c.exists():
            return c

    return candidates[0] if candidates else Path("models/face_landmarker.task")


class ITrackerAdapter(ABC):
    """Abstract interface for face landmark tracking."""

    @abstractmethod
    def detect(self, packet: FramePacket) -> LandmarkPacket:
        """Process a frame packet and return validated landmarks."""

    @abstractmethod
    def close(self) -> None:
        """Release tracker resources."""


class MediaPipeFaceTracker(ITrackerAdapter):
    """MediaPipe Face Landmarker Task implementation."""

    def __init__(self, model_asset_path: str | Path | None = None):
        self.model_path = resolve_model_asset_path(model_asset_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"MediaPipe task asset not found at {self.model_path}. "
                "Please run scripts/fetch_models.ps1 or scripts/doctor.ps1."
            )

        base_options = python.BaseOptions(model_asset_path=str(self.model_path))
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=2,  # Must detect at least 2 faces to enforce exactly-one-face policy
            running_mode=vision.RunningMode.IMAGE,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

    def detect(self, packet: FramePacket) -> LandmarkPacket:
        """Process a frame and enforce the exactly-one-face safety invariant."""
        t_infer_start = time.perf_counter_ns()
        try:
            # OpenCV provides BGR; MediaPipe expects RGB
            rgb_image = cv2.cvtColor(packet.bgr_image, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

            detection_result = self._landmarker.detect(mp_image)
            t_infer_end = time.perf_counter_ns()
            face_count = len(detection_result.face_landmarks)

            if face_count == 0:
                return LandmarkPacket(
                    frame_id=packet.frame_id,
                    t_ns=packet.captured_at_monotonic_ns,
                    face_count=0,
                    normalized_landmarks=None,
                    valid=False,
                    failure_reason="NO_FACE_DETECTED",
                    t_read_start_ns=packet.t_read_start_ns,
                    t_queue_insert_ns=packet.t_queue_insert_ns,
                    t_queue_remove_ns=packet.t_queue_remove_ns,
                    t_infer_start_ns=t_infer_start,
                    t_infer_end_ns=t_infer_end,
                )

            if face_count > 1:
                return LandmarkPacket(
                    frame_id=packet.frame_id,
                    t_ns=packet.captured_at_monotonic_ns,
                    face_count=face_count,
                    normalized_landmarks=None,
                    valid=False,
                    failure_reason=f"MULTIPLE_FACES_DETECTED ({face_count} faces in view)",
                    t_read_start_ns=packet.t_read_start_ns,
                    t_queue_insert_ns=packet.t_queue_insert_ns,
                    t_queue_remove_ns=packet.t_queue_remove_ns,
                    t_infer_start_ns=t_infer_start,
                    t_infer_end_ns=t_infer_end,
                )

            # Exactly one face detected: extract 478 landmarks
            raw_landmarks = detection_result.face_landmarks[0]
            landmarks_arr = np.array([[lm.x, lm.y, lm.z] for lm in raw_landmarks], dtype=np.float64)

            # Extract blendshapes
            blendshapes_dict: dict[str, float] = {}
            if detection_result.face_blendshapes and len(detection_result.face_blendshapes) > 0:
                for category in detection_result.face_blendshapes[0]:
                    blendshapes_dict[category.category_name] = float(category.score)

            return LandmarkPacket(
                frame_id=packet.frame_id,
                t_ns=packet.captured_at_monotonic_ns,
                face_count=1,
                normalized_landmarks=landmarks_arr,
                blendshapes=blendshapes_dict,
                valid=True,
                failure_reason="",
                t_read_start_ns=packet.t_read_start_ns,
                t_queue_insert_ns=packet.t_queue_insert_ns,
                t_queue_remove_ns=packet.t_queue_remove_ns,
                t_infer_start_ns=t_infer_start,
                t_infer_end_ns=t_infer_end,
            )

        except Exception as e:
            t_infer_end = time.perf_counter_ns()
            return LandmarkPacket(
                frame_id=packet.frame_id,
                t_ns=packet.captured_at_monotonic_ns,
                face_count=0,
                normalized_landmarks=None,
                valid=False,
                failure_reason=f"TRACKER_ERROR: {str(e)}",
                t_read_start_ns=packet.t_read_start_ns,
                t_queue_insert_ns=packet.t_queue_insert_ns,
                t_queue_remove_ns=packet.t_queue_remove_ns,
                t_infer_start_ns=t_infer_start,
                t_infer_end_ns=t_infer_end,
            )

    def close(self) -> None:
        """Safely close MediaPipe landmarker."""
        if hasattr(self, "_landmarker") and self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                pass


class SimulatedFaceTracker(ITrackerAdapter):
    """Simulated tracker returning programmed landmark sequences for deterministic testing."""

    def __init__(self, responses: list[LandmarkPacket] | None = None):
        self.responses = responses or []
        self._idx = 0

    def detect(self, packet: FramePacket) -> LandmarkPacket:
        if not self.responses:
            # Default to valid synthetic face
            coords = np.zeros((478, 3), dtype=np.float64)
            # Dummy eye corners to give realistic inter-ocular distance
            coords[33] = [0.35, 0.45, 0.0]  # Left outer eye
            coords[263] = [0.65, 0.45, 0.0]  # Right outer eye
            coords[105] = [0.40, 0.35, 0.0]  # Left brow
            coords[334] = [0.60, 0.35, 0.0]  # Right brow
            coords[13] = [0.50, 0.65, 0.0]  # Upper lip
            coords[14] = [0.50, 0.70, 0.0]  # Lower lip
            coords[1] = [0.50, 0.50, 0.0]  # Nose tip
            coords[152] = [0.50, 0.85, 0.0]  # Chin
            return LandmarkPacket(
                frame_id=packet.frame_id,
                t_ns=packet.captured_at_monotonic_ns,
                face_count=1,
                normalized_landmarks=coords,
                valid=True,
                failure_reason="",
                t_read_start_ns=packet.t_read_start_ns,
                t_queue_insert_ns=packet.t_queue_insert_ns,
                t_queue_remove_ns=packet.t_queue_remove_ns,
            )

        resp = self.responses[self._idx % len(self.responses)]
        self._idx += 1
        return resp

    def close(self) -> None:
        pass
