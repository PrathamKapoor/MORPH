"""Unit tests for RecognitionConfig and threshold validation."""

import pytest

from morph.common.config import RecognitionConfig


def test_default_config_is_valid():
    config = RecognitionConfig()
    config.validate()  # Should not raise


def test_config_invalid_hold():
    config = RecognitionConfig(hold_ms=10)  # Too small (<50)
    with pytest.raises(ValueError, match="hold_ms"):
        config.validate()


def test_config_invalid_release():
    config = RecognitionConfig(release_ms=2000)  # Too large (>1000)
    with pytest.raises(ValueError, match="release_ms"):
        config.validate()


def test_config_invalid_similarity():
    config = RecognitionConfig(min_similarity=1.5)  # > 0.99
    with pytest.raises(ValueError, match="min_similarity"):
        config.validate()


def test_config_invalid_margin():
    config = RecognitionConfig(min_margin=-0.1)  # < 0.0
    with pytest.raises(ValueError, match="min_margin"):
        config.validate()


def test_config_invalid_queue_size():
    config = RecognitionConfig(bounded_queue_size=0)
    with pytest.raises(ValueError, match="bounded_queue_size"):
        config.validate()
