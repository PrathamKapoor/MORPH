"""Synthetic facial landmark fixtures for algorithm unit tests.

Explicitly labeled SYNTHETIC_FIXTURE. Not human clinical data.
Re-exported from morph.evaluation.fixtures for backward compatibility with test suite.
"""

from __future__ import annotations

from morph.evaluation.fixtures import (
    create_synthetic_brow_raise_landmarks,
    create_synthetic_held_out_landmarks,
    create_synthetic_mouth_open_landmarks,
    create_synthetic_neutral_landmarks,
    create_synthetic_noise_landmarks,
    create_synthetic_smile_landmarks,
)

__all__ = [
    "create_synthetic_brow_raise_landmarks",
    "create_synthetic_held_out_landmarks",
    "create_synthetic_mouth_open_landmarks",
    "create_synthetic_neutral_landmarks",
    "create_synthetic_noise_landmarks",
    "create_synthetic_smile_landmarks",
]
