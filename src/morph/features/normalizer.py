"""Scale-invariant, neutral-relative feature extraction for MORPH 2.0."""

from __future__ import annotations

import numpy as np

from morph.common.types import FeaturePacket, LandmarkPacket


class FeatureExtractor:
    """Extracts 32-dimensional normalized feature vectors from LandmarkPackets."""

    SCHEMA_VERSION = "morph-features-v1.0"

    BLENDSHAPE_KEYS = [
        "browDownLeft",
        "browDownRight",
        "browInnerUp",
        "browOuterUpLeft",
        "browOuterUpRight",
        "mouthSmileLeft",
        "mouthSmileRight",
        "mouthOpen",
        "jawOpen",
        "mouthPucker",
        "eyeBlinkLeft",
        "eyeBlinkRight",
        "eyeSquintLeft",
        "eyeSquintRight",
        "cheekPuff",
        "mouthShrugLower",
    ]

    def __init__(
        self,
        neutral_landmarks: np.ndarray | None = None,
        neutral_interocular: float | None = None,
    ):
        self.neutral_landmarks = neutral_landmarks
        self.neutral_interocular = neutral_interocular

    def set_neutral_baseline(
        self, neutral_landmarks: np.ndarray, neutral_interocular: float
    ) -> None:
        """Set the calibrated resting neutral baseline landmarks and scale."""
        if neutral_landmarks.shape != (478, 3):
            raise ValueError(
                f"Neutral landmarks must have shape (478, 3), got {neutral_landmarks.shape}"
            )
        if neutral_interocular <= 1e-4:
            raise ValueError(f"Inter-ocular distance too small: {neutral_interocular}")
        self.neutral_landmarks = neutral_landmarks.copy()
        self.neutral_interocular = float(neutral_interocular)

    def clear_baseline(self) -> None:
        """Reset the resting neutral baseline landmarks and scale to uncalibrated."""
        self.neutral_landmarks = None
        self.neutral_interocular = None

    def extract(self, packet: LandmarkPacket) -> FeaturePacket:
        """Extract and normalize feature vector from landmark packet."""
        if not packet.valid or packet.normalized_landmarks is None:
            return FeaturePacket(
                frame_id=packet.frame_id,
                t_ns=packet.t_ns,
                feature_schema_version=self.SCHEMA_VERSION,
                vector=np.zeros(32, dtype=np.float64),
                valid=False,
                quality=0.0,
                validity_reason=packet.failure_reason or "INVALID_LANDMARK_PACKET",
            )

        lm = packet.normalized_landmarks  # Shape (478, 3)

        # 1. Compute current inter-ocular distance (outer eye corners: 33 and 263)
        left_eye = lm[33]
        right_eye = lm[263]
        current_eye_dist = float(np.linalg.norm(right_eye - left_eye))

        if current_eye_dist < 1e-4:
            return FeaturePacket(
                frame_id=packet.frame_id,
                t_ns=packet.t_ns,
                feature_schema_version=self.SCHEMA_VERSION,
                vector=np.zeros(32, dtype=np.float64),
                valid=False,
                quality=0.0,
                validity_reason="EYE_DISTANCE_COLLAPSED",
            )

        # Reference scale is neutral if available, else current
        scale = self.neutral_interocular if self.neutral_interocular else current_eye_dist

        # Compute displacements relative to neutral baseline if calibrated
        if self.neutral_landmarks is not None:
            neutral = self.neutral_landmarks
            diff = (lm - neutral) / scale
        else:
            diff = np.zeros_like(lm)

        # 2. Extract 16 Geometric Displacement Dimensions (All relative to neutral baseline)
        # Note: In normalized screen coordinates, y increases downward.
        # Moving eyebrows up means y decreases, so -diff[105, 1] is positive for upward brow raise.
        geom = np.zeros(16, dtype=np.float64)
        geom[0] = -diff[105, 1]  # Left brow elevation
        geom[1] = -diff[334, 1]  # Right brow elevation
        geom[2] = geom[0] - geom[1]  # Brow asymmetry
        geom[3] = diff[14, 1] - diff[13, 1]  # Vertical mouth opening change
        geom[4] = diff[291, 0] - diff[61, 0]  # Horizontal mouth width change
        geom[5] = -diff[61, 0]  # Left mouth corner horizontal pull
        geom[6] = -diff[61, 1]  # Left mouth corner elevation
        geom[7] = diff[291, 0]  # Right mouth corner horizontal pull
        geom[8] = -diff[291, 1]  # Right mouth corner elevation
        geom[9] = diff[152, 1]  # Chin vertical drop
        geom[10] = diff[1, 0]  # Nose tip horizontal yaw
        geom[11] = diff[1, 1]  # Nose tip vertical pitch

        if self.neutral_landmarks is not None:
            n_lm = self.neutral_landmarks
            geom[12] = (
                float(np.linalg.norm(lm[105] - lm[468]))
                - float(np.linalg.norm(n_lm[105] - n_lm[468]))
            ) / scale
            geom[13] = (
                float(np.linalg.norm(lm[334] - lm[473]))
                - float(np.linalg.norm(n_lm[334] - n_lm[473]))
            ) / scale
            geom[14] = (
                float(np.linalg.norm(lm[14] - lm[152]))
                - float(np.linalg.norm(n_lm[14] - n_lm[152]))
            ) / scale
            geom[15] = (
                float(np.linalg.norm(lm[1] - lm[13])) - float(np.linalg.norm(n_lm[1] - n_lm[13]))
            ) / scale
        else:
            geom[12] = 0.0
            geom[13] = 0.0
            geom[14] = 0.0
            geom[15] = 0.0

        # 3. Extract 16 Blendshape Dimensions
        blend = np.zeros(16, dtype=np.float64)
        for i, key in enumerate(self.BLENDSHAPE_KEYS):
            blend[i] = packet.blendshapes.get(key, 0.0)

        # Combine into 32-D vector
        full_vector = np.concatenate([geom, blend])

        # Verify finitude
        if not np.all(np.isfinite(full_vector)):
            return FeaturePacket(
                frame_id=packet.frame_id,
                t_ns=packet.t_ns,
                feature_schema_version=self.SCHEMA_VERSION,
                vector=np.zeros(32, dtype=np.float64),
                valid=False,
                quality=0.0,
                validity_reason="NON_FINITE_FEATURE_VALUES",
            )

        # Quality estimation based on eye distance scale and landmark confidence
        quality = float(min(1.0, max(0.0, current_eye_dist / 0.35)))

        return FeaturePacket(
            frame_id=packet.frame_id,
            t_ns=packet.t_ns,
            feature_schema_version=self.SCHEMA_VERSION,
            vector=full_vector,
            valid=True,
            quality=quality,
            validity_reason="",
        )
