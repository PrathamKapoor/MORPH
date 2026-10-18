"""Unit tests for offline Text-to-Speech adapters."""

from morph.actions.tts import MockTTSAdapter


def test_mock_tts_adapter():
    tts = MockTTSAdapter()
    assert tts.speak("I need water") is True
    assert tts.speak("Thank you") is True
    assert tts.speak("") is False  # Empty string rejected

    assert tts.spoken_phrases == ["I need water", "Thank you"]
