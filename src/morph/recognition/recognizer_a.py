"""Condition A: Generic Fixed-Threshold Baseline Recognizer."""

from __future__ import annotations

from morph.common.types import FeaturePacket, RecognitionResult


class BaselineRecognizerA:
    """Condition A: Simple fixed anatomical motion thresholds.

    Not purposely crippled: includes noise deadband and reasonable thresholds.
    Fires immediately on first frame exceeding threshold.
    """

    VERSION = "baseline-fixed-a-v1.0"

    def __init__(
        self,
        brow_thresh: float = 0.08,
        smile_thresh: float = 0.09,
        mouth_open_thresh: float = 0.08,
    ):
        self.brow_thresh = brow_thresh
        self.smile_thresh = smile_thresh
        self.mouth_open_thresh = mouth_open_thresh

    def predict(self, packet: FeaturePacket) -> RecognitionResult:
        """Evaluate fixed threshold rules against feature packet."""
        if not packet.valid or packet.vector is None:
            return RecognitionResult(
                frame_id=packet.frame_id,
                t_ns=packet.t_ns,
                label_scores={},
                best_label="UNKNOWN",
                second_label="UNKNOWN",
                accepted_candidate_or_none=None,
                reject_reason=packet.validity_reason or "INVALID_FEATURE_PACKET",
                recognizer_version=self.VERSION,
            )

        v = packet.vector
        # Geometric displacements (v[0..15])
        # v[0]: left brow elevation, v[1]: right brow elevation
        # v[3]: vertical mouth opening, v[4]: horizontal mouth width change, v[9]: chin drop
        brow_geom = max(float(v[0]), float(v[1]))
        smile_geom = float(v[4])
        mouth_geom = max(float(v[3]), float(v[9]) if len(v) > 9 else 0.0)

        # Blendshapes (v[16..31]) if available
        # 16: browDownLeft, 17: browDownRight, 18: browInnerUp, 19: browOuterUpLeft, 20: browOuterUpRight
        # 21: mouthSmileLeft, 22: mouthSmileRight, 23: mouthOpen, 24: jawOpen
        brow_blend = max(float(v[18]), float(v[19]), float(v[20])) if len(v) >= 21 else 0.0
        smile_blend = max(float(v[21]), float(v[22])) if len(v) >= 23 else 0.0
        mouth_blend = max(float(v[23]), float(v[24])) if len(v) >= 25 else 0.0

        brow_val = max(brow_geom, brow_blend)
        smile_val = max(smile_geom, smile_blend)
        mouth_val = max(mouth_geom, mouth_blend)

        scores = {
            "Brow Raise": brow_val,
            "Smile / Lip Corner Pull": smile_val,
            "Chin Raise / Mouth Open": mouth_val,
        }

        # Determine threshold breaches
        candidates = []
        if brow_val >= self.brow_thresh:
            candidates.append(("Brow Raise", brow_val))
        if smile_val >= self.smile_thresh:
            candidates.append(("Smile / Lip Corner Pull", smile_val))
        if mouth_val >= self.mouth_open_thresh:
            candidates.append(("Chin Raise / Mouth Open", mouth_val))

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_lbl, best_sc = sorted_scores[0]
        second_lbl, second_sc = sorted_scores[1]

        if not candidates:
            return RecognitionResult(
                frame_id=packet.frame_id,
                t_ns=packet.t_ns,
                label_scores=scores,
                best_label=best_lbl,
                second_label=second_lbl,
                accepted_candidate_or_none=None,
                reject_reason="ALL_SCORES_BELOW_FIXED_THRESHOLDS",
                recognizer_version=self.VERSION,
            )

        if len(candidates) > 1:
            # Conflict between thresholds
            return RecognitionResult(
                frame_id=packet.frame_id,
                t_ns=packet.t_ns,
                label_scores=scores,
                best_label=best_lbl,
                second_label=second_lbl,
                accepted_candidate_or_none=None,
                reject_reason=f"CONFLICT_MULTIPLE_THRESHOLDS_BREACHED ({[c[0] for c in candidates]})",
                recognizer_version=self.VERSION,
            )

        chosen_label = candidates[0][0]
        return RecognitionResult(
            frame_id=packet.frame_id,
            t_ns=packet.t_ns,
            label_scores=scores,
            best_label=chosen_label,
            second_label=second_lbl if second_lbl != chosen_label else "UNKNOWN",
            accepted_candidate_or_none=chosen_label,
            reject_reason="",
            recognizer_version=self.VERSION,
        )
