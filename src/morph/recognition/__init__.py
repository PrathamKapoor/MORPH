"""Recognition engines: Condition A (fixed thresholds) and Condition B (personalized prototype)."""

from morph.recognition.recognizer_a import BaselineRecognizerA
from morph.recognition.recognizer_b import PersonalizedRecognizerB

__all__ = ["BaselineRecognizerA", "PersonalizedRecognizerB"]
