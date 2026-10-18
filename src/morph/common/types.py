"""Typed data contracts and immutable schemas for MORPH 2.0."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class State(str, Enum):
    """Pure finite-state machine states for the IntentEngine."""

    PAUSED = "PAUSED"
    TRACKING_LOST = "TRACKING_LOST"
    IDLE = "IDLE"
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    COOLDOWN = "COOLDOWN"


class ActionType(str, Enum):
    """Strictly allow-listed AAC actions."""

    NEXT_TILE = "NEXT_TILE"
    PREVIOUS_TILE = "PREVIOUS_TILE"
    SELECT_TILE = "SELECT_TILE"
    SPEAK_TILE = "SPEAK_TILE"
    BACK = "BACK"
    PAUSE = "PAUSE"


class SourceMode(str, Enum):
    """Explicit source mode distinguishing live optical sensors, replay, and synthetic fixtures."""

    PHYSICAL_CAMERA = "PHYSICAL_CAMERA"
    RECORDED_REPLAY = "RECORDED_REPLAY"
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    CAMERA_UNAVAILABLE = "CAMERA_UNAVAILABLE"


@dataclass(frozen=True)
class FramePacket:
    """Raw camera capture packet.

    bgr_image resides strictly in volatile memory and is never serialized.
    """

    frame_id: int
    captured_at_monotonic_ns: int
    bgr_image: np.ndarray
    source_id: str = "webcam_0"
    t_read_start_ns: int = 0
    t_queue_insert_ns: int = 0
    t_queue_remove_ns: int = 0

    def __post_init__(self):
        if self.frame_id < 0:
            raise ValueError(f"frame_id must be non-negative, got {self.frame_id}")
        if self.captured_at_monotonic_ns < 0:
            raise ValueError(
                f"captured_at_monotonic_ns must be non-negative, got {self.captured_at_monotonic_ns}"
            )
        if not isinstance(self.bgr_image, np.ndarray):
            raise TypeError("bgr_image must be a numpy ndarray")


@dataclass(frozen=True)
class LandmarkPacket:
    """Landmark packet produced by MediaPipe FaceLandmarker."""

    frame_id: int
    t_ns: int
    face_count: int
    normalized_landmarks: np.ndarray | None  # Shape (478, 3) or None
    blendshapes: dict[str, float] = field(default_factory=dict)
    valid: bool = False
    failure_reason: str = ""
    tracker_model_version: str = "FaceLandmarker-v1"
    t_read_start_ns: int = 0
    t_queue_insert_ns: int = 0
    t_queue_remove_ns: int = 0
    t_infer_start_ns: int = 0
    t_infer_end_ns: int = 0

    @property
    def captured_at_monotonic_ns(self) -> int:
        """Alias for t_ns for backward-compatible pipeline stage measurement."""
        return self.t_ns

    def __post_init__(self):
        if self.frame_id < 0:
            raise ValueError(f"frame_id must be non-negative, got {self.frame_id}")
        if self.t_ns < 0:
            raise ValueError(f"t_ns must be non-negative, got {self.t_ns}")


@dataclass(frozen=True)
class FeaturePacket:
    """Normalized feature vector for classification and intention gating."""

    frame_id: int
    t_ns: int
    feature_schema_version: str
    vector: np.ndarray  # 1D array of float64
    valid: bool
    quality: float  # 0.0 to 1.0
    validity_reason: str = ""
    profile_neutral_version: str = "default_neutral"

    def __post_init__(self):
        if self.frame_id < 0:
            raise ValueError(f"frame_id must be non-negative, got {self.frame_id}")
        if self.t_ns < 0:
            raise ValueError(f"t_ns must be non-negative, got {self.t_ns}")
        if self.valid:
            if not isinstance(self.vector, np.ndarray):
                raise TypeError("vector must be a numpy ndarray")
            if self.vector.ndim != 1:
                raise ValueError(f"vector must be 1-dimensional, got ndim={self.vector.ndim}")
            # Strict NaN / Inf check
            if not np.all(np.isfinite(self.vector)):
                object.__setattr__(self, "valid", False)
                object.__setattr__(
                    self, "validity_reason", "Vector contains non-finite values (NaN/Inf)"
                )
            if not (0.0 <= self.quality <= 1.0) or math.isnan(self.quality):
                object.__setattr__(self, "valid", False)
                object.__setattr__(
                    self, "validity_reason", f"Quality score out of bounds: {self.quality}"
                )


@dataclass(frozen=True)
class RecognitionResult:
    """Output of classification layer (Condition B)."""

    frame_id: int
    t_ns: int
    label_scores: dict[str, float]
    best_label: str
    second_label: str
    accepted_candidate_or_none: str | None
    reject_reason: str
    recognizer_version: str = "prototype-v1"
    profile_version: str = "profile-v1"


@dataclass(frozen=True)
class IntentTransition:
    """Record of an IntentEngine state machine transition."""

    t_ns: int
    before: State
    after: State
    label_or_none: str | None
    reason: str
    config_version: str
    frame_id: int


@dataclass(frozen=True)
class ConfirmedCommand:
    """Command event emitted upon successful confirmation by IntentEngine."""

    command_event_uuid: str
    frame_id: int
    confirmed_at_ns: int
    gesture_uuid: str
    action_mapping_uuid: str
    version_snapshot: str


@dataclass(frozen=True)
class ActionResult:
    """Result of an action executed by ActionDispatcher."""

    command_event_uuid: str
    action_name: str
    dispatched_at_ns: int
    success: bool
    safe_error_code: str = ""


class GroundTruthLabelType(str, Enum):
    """Categorical classification of evaluation ground-truth observations."""

    CORRECT_GESTURE = "CORRECT_GESTURE"
    INCORRECT_GESTURE = "INCORRECT_GESTURE"
    NO_GESTURE = "NO_GESTURE"
    AMBIGUOUS_OBSERVATION = "AMBIGUOUS_OBSERVATION"
    TRACKING_INVALID = "TRACKING_INVALID"
    ANNOTATION_UNCERTAIN = "ANNOTATION_UNCERTAIN"
    UNLABELED_PERIOD = "UNLABELED_PERIOD"


class EvaluationScenario(str, Enum):
    """Controlled research evaluation scenario identifiers (Milestone M8.2)."""

    SCEN_01_INTENDED = "SCEN-01-INTENDED-GESTURES"
    SCEN_02_NEUTRAL = "SCEN-02-NEUTRAL-REST"
    SCEN_03_DISTRACTOR = "SCEN-03-DISTRACTOR-MOVEMENTS"
    SCEN_04_BOARD_TASK = "SCEN-04-COMMUNICATION-BOARD"
    SCEN_05_PAUSE_RECOVERY = "SCEN-05-PAUSE-TRACKING-RECOVERY"
    SCEN_06_CAMERA_DRIFT = "SCEN-06-CAMERA-HEAD-POSE-CHANGE"
    SCEN_07_CROSS_SESSION = "SCEN-07-CROSS-SESSION-RETEST"
    SCEN_08_RECALIBRATION = "SCEN-08-RECALIBRATION-COMPARISON"


class AnnotationSource(str, Enum):
    """Origin of a ground-truth label."""

    TASK_PROMPT = "TASK_PROMPT"
    OPERATOR = "OPERATOR"
    PARTICIPANT_CONFIRMED = "PARTICIPANT_CONFIRMED"


@dataclass(frozen=True)
class GroundTruthEvent:
    """Annotated ground truth event for research evaluation."""

    label: str
    start_ns: int
    end_ns: int
    annotator: str
    session_id: str
    event_uuid: str = ""
    label_type: str = "CORRECT_GESTURE"
    revision: int = 1
    notes: str = ""
    annotation_source: str = "TASK_PROMPT"
    is_reviewed: bool = False

    def __post_init__(self):
        if self.start_ns < 0 or self.end_ns < 0:
            raise ValueError("Timestamps must be non-negative")
        if self.end_ns < self.start_ns:
            raise ValueError(
                f"end_ns ({self.end_ns}) cannot be earlier than start_ns ({self.start_ns})"
            )


@dataclass(frozen=True)
class TrackingHealth:
    """Live tracking and worker health telemetry."""

    processed_fps: float
    capture_fps: float
    dropped_frames: int
    stale_frames: int
    face_count: int
    last_block_reason: str
    camera_connected: bool
    out_of_order_frames: int = 0
    source_mode: SourceMode = SourceMode.PHYSICAL_CAMERA
