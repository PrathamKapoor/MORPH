"""Sample quality assessment and outlier filtering for MORPH 2.0."""

from __future__ import annotations

import numpy as np

from morph.common.types import LandmarkPacket


def assess_sample_quality(packet: LandmarkPacket) -> tuple[bool, float, str]:
    """Assess whether a landmark packet meets criteria for enrollment training.

    Returns:
        (is_acceptable, quality_score, rejection_reason)
    """
    if not packet.valid or packet.normalized_landmarks is None:
        return False, 0.0, packet.failure_reason or "INVALID_LANDMARK_DATA"

    if packet.face_count != 1:
        return (
            False,
            0.0,
            f"MULTIPLE_FACES ({packet.face_count}) - Exactly one face required",
        )

    lm = packet.normalized_landmarks

    # 1. Check face framing boundary: landmarks must be within [0.05, 0.95] screen bounds
    min_x, max_x = float(np.min(lm[:, 0])), float(np.max(lm[:, 0]))
    min_y, max_y = float(np.min(lm[:, 1])), float(np.max(lm[:, 1]))

    if min_x < 0.02 or max_x > 0.98 or min_y < 0.02 or max_y > 0.98:
        return False, 0.3, "FACE_TOO_CLOSE_TO_FRAME_BOUNDARY"

    # 2. Check inter-ocular distance: face must not be too far away
    eye_dist = float(np.linalg.norm(lm[263] - lm[33]))
    if eye_dist < 0.10:
        return False, 0.4, "FACE_TOO_FAR_FROM_CAMERA"

    # 3. Check head roll/yaw symmetry
    # Y-difference between eyes indicates head tilt/roll
    eye_y_diff = abs(lm[263, 1] - lm[33, 1])
    if eye_y_diff > 0.15:
        return False, 0.5, "HEAD_TILT_TOO_STEEP"

    # Quality score based on centering and scale
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    dist_from_center = float(np.sqrt((center_x - 0.5) ** 2 + (center_y - 0.5) ** 2))
    centering_score = max(0.0, 1.0 - dist_from_center * 2.0)

    quality = float(min(1.0, 0.6 * (eye_dist / 0.3) + 0.4 * centering_score))
    return True, quality, ""
