"""Synthetic facial landmark fixtures for algorithm unit tests.

Explicitly labeled SYNTHETIC_FIXTURE. Not human clinical data.
"""

from __future__ import annotations

import numpy as np


def create_synthetic_neutral_landmarks() -> np.ndarray:
    """Create a realistic synthetic 478-point resting face mesh."""
    lm = np.zeros((478, 3), dtype=np.float64)
    # Eye corners (inter-ocular distance = 0.30 in normalized coords)
    lm[33] = [0.35, 0.45, 0.0]  # Left outer eye corner
    lm[263] = [0.65, 0.45, 0.0]  # Right outer eye corner
    lm[468] = [0.40, 0.45, 0.0]  # Left pupil center
    lm[473] = [0.60, 0.45, 0.0]  # Right pupil center

    # Eyebrows
    lm[105] = [0.40, 0.38, 0.0]  # Left eyebrow center
    lm[334] = [0.60, 0.38, 0.0]  # Right eyebrow center

    # Mouth and lips
    lm[13] = [0.50, 0.65, 0.0]  # Upper lip center
    lm[14] = [0.50, 0.68, 0.0]  # Lower lip center
    lm[61] = [0.42, 0.66, 0.0]  # Left mouth corner
    lm[291] = [0.58, 0.66, 0.0]  # Right mouth corner

    # Nose and chin
    lm[1] = [0.50, 0.52, 0.0]  # Nose tip
    lm[152] = [0.50, 0.85, 0.0]  # Chin

    # Fill remaining indices with reasonable coordinates
    for i in range(478):
        if lm[i, 0] == 0.0:
            lm[i] = [0.50 + 0.001 * (i % 20), 0.50 + 0.001 * (i // 20), 0.0]
    return lm


def create_synthetic_brow_raise_landmarks() -> np.ndarray:
    """Synthetic face with elevated eyebrows (-y is upward)."""
    lm = create_synthetic_neutral_landmarks()
    # Lift eyebrows upward by 0.04 screen units (~0.13 normalized units)
    lm[105, 1] -= 0.04
    lm[334, 1] -= 0.04
    return lm


def create_synthetic_smile_landmarks() -> np.ndarray:
    """Synthetic face with mouth pulled wide horizontally and elevated."""
    lm = create_synthetic_neutral_landmarks()
    # Pull corners outwards
    lm[61, 0] -= 0.03
    lm[291, 0] += 0.03
    # Pull corners slightly up
    lm[61, 1] -= 0.015
    lm[291, 1] -= 0.015
    return lm


def create_synthetic_mouth_open_landmarks() -> np.ndarray:
    """Synthetic face with lower lip and chin dropped downwards."""
    lm = create_synthetic_neutral_landmarks()
    lm[14, 1] += 0.04
    lm[152, 1] += 0.03
    return lm


def create_synthetic_noise_landmarks() -> np.ndarray:
    """Synthetic face with slight non-command noise/twitch."""
    lm = create_synthetic_neutral_landmarks()
    rng = np.random.default_rng(42)
    lm += rng.normal(0, 0.002, lm.shape)
    return lm


def create_synthetic_held_out_landmarks(
    base_type: str = "neutral",
    scale_offset: float = 0.0,
    yaw_offset: float = 0.0,
    pitch_offset: float = 0.0,
    intensity: float = 1.0,
    seed: int = 42,
) -> np.ndarray:
    """Create held-out synthetic facial landmarks with controlled physiological variations.

    Guarantees that evaluation frames differ from calibration prototypes while preserving
    valid semantic gesture characteristics.
    """
    if base_type == "brow_raise":
        base = create_synthetic_neutral_landmarks()
        base[105, 1] -= 0.04 * intensity
        base[334, 1] -= 0.04 * intensity
    elif base_type == "smile":
        base = create_synthetic_neutral_landmarks()
        base[61, 0] -= 0.03 * intensity
        base[291, 0] += 0.03 * intensity
        base[61, 1] -= 0.015 * intensity
        base[291, 1] -= 0.015 * intensity
    elif base_type == "mouth_open":
        base = create_synthetic_neutral_landmarks()
        base[14, 1] += 0.04 * intensity
        base[152, 1] += 0.03 * intensity
    else:
        base = create_synthetic_neutral_landmarks()

    # Apply scale offset relative to nose center
    if abs(scale_offset) > 1e-6:
        center = base[1].copy()
        base = center + (base - center) * (1.0 + scale_offset)

    # Apply head pose offsets (yaw and pitch)
    if abs(yaw_offset) > 1e-6:
        base[:, 0] += yaw_offset
    if abs(pitch_offset) > 1e-6:
        base[:, 1] += pitch_offset

    # Apply subtle deterministic physiological noise
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, 0.0003, base.shape)
    return base + noise
