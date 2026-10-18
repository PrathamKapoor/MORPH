"""Offline Windows SAPI Text-to-Speech (TTS) adapters for MORPH 2.0."""

from __future__ import annotations

import queue
import threading
from abc import ABC, abstractmethod

import pyttsx3


class ITextToSpeechAdapter(ABC):
    """Abstract interface for speech synthesis adapters."""

    @abstractmethod
    def speak(self, text: str) -> bool:
        """Enqueue phrase for speech output."""

    @abstractmethod
    def stop(self) -> None:
        """Interrupt and cancel ongoing speech."""

    @abstractmethod
    def close(self) -> None:
        """Release TTS resources."""


class WindowsSapiTTS(ITextToSpeechAdapter):
    """Local, offline Windows SAPI TTS synthesizer running on a dedicated thread."""

    def __init__(self, voice_name: str | None = None, rate: int = 150):
        self.voice_name = voice_name
        self.rate = rate
        self._queue: queue.Queue[str] = queue.Queue()
        self._running = True

        self._thread = threading.Thread(target=self._speech_worker, daemon=True)
        self._thread.start()

    def _speech_worker(self) -> None:
        """Dedicated worker thread running pyttsx3 loop to prevent blocking UI."""
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)

            # Select voice if specified
            if self.voice_name:
                voices = engine.getProperty("voices")
                for v in voices:
                    if self.voice_name.lower() in v.name.lower():
                        engine.setProperty("voice", v.id)
                        break

            while self._running:
                try:
                    phrase = self._queue.get(timeout=0.2)
                    if phrase is None or not self._running:
                        break
                    engine.say(phrase)
                    engine.runAndWait()
                    self._queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"[TTS Worker Error]: {e}")
        except Exception as e:
            print(f"[TTS Initialization Error]: {e}")

    def speak(self, text: str) -> bool:
        """Enqueue speech request without blocking."""
        if not text or not self._running:
            return False
        self._queue.put(text)
        return True

    def stop(self) -> None:
        """Clear queued speech items."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

    def close(self) -> None:
        """Gracefully shutdown worker thread."""
        self._running = False
        self._queue.put(None)  # Sentinel


class MockTTSAdapter(ITextToSpeechAdapter):
    """Deterministic in-memory mock TTS for unit tests and benchmarks."""

    def __init__(self):
        self.spoken_phrases: list[str] = []

    def speak(self, text: str) -> bool:
        if text:
            self.spoken_phrases.append(text)
            return True
        return False

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass
