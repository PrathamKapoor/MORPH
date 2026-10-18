"""Configuration schemas and validation for MORPH 2.0."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecognitionConfig:
    """Configurable timing and classification thresholds.

    Marked conservative UNVALIDATED_DEFAULTS until tuned per participant.
    """

    hold_ms: int = 300
    release_ms: int = 150
    cooldown_ms: int = 300
    min_similarity: float = 0.65
    min_margin: float = 0.15
    max_frame_age_ms: int = 100
    bounded_queue_size: int = 2
    camera_index: int = 0
    target_fps: int = 30
    config_version: str = "config-v1.0"
    rearm_neutral_dwell_ms: int = 200

    def validate(self) -> None:
        """Validate all parameters and raise ValueError on invalid ranges."""
        if self.hold_ms < 50 or self.hold_ms > 2000:
            raise ValueError(f"hold_ms must be between 50 and 2000 ms, got {self.hold_ms}")
        if self.release_ms < 50 or self.release_ms > 1000:
            raise ValueError(f"release_ms must be between 50 and 1000 ms, got {self.release_ms}")
        if self.cooldown_ms < 50 or self.cooldown_ms > 3000:
            raise ValueError(f"cooldown_ms must be between 50 and 3000 ms, got {self.cooldown_ms}")
        if not (0.1 <= self.min_similarity <= 0.99):
            raise ValueError(
                f"min_similarity must be between 0.1 and 0.99, got {self.min_similarity}"
            )
        if not (0.0 <= self.min_margin <= 0.5):
            raise ValueError(f"min_margin must be between 0.0 and 0.5, got {self.min_margin}")
        if self.max_frame_age_ms < 20 or self.max_frame_age_ms > 500:
            raise ValueError(
                f"max_frame_age_ms must be between 20 and 500 ms, got {self.max_frame_age_ms}"
            )
        if self.bounded_queue_size < 1 or self.bounded_queue_size > 10:
            raise ValueError(
                f"bounded_queue_size must be between 1 and 10, got {self.bounded_queue_size}"
            )
        if self.rearm_neutral_dwell_ms < 50:
            raise ValueError("rearm_neutral_dwell_ms must be at least 50 ms")
