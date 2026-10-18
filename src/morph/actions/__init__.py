"""Action execution, sandboxed dispatcher, and offline TTS adapters."""

from morph.actions.dispatcher import ActionDispatcher, NoOpActionSink
from morph.actions.tts import ITextToSpeechAdapter, MockTTSAdapter, WindowsSapiTTS

__all__ = [
    "ActionDispatcher",
    "ITextToSpeechAdapter",
    "MockTTSAdapter",
    "NoOpActionSink",
    "WindowsSapiTTS",
]
