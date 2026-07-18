"""Abstract interfaces for Sumo's swappable pipeline stages.

The whole point of this module is that the main loop (``sumo/app.py``) only ever
talks to these abstractions. The concrete Vosk / pyttsx3 implementations live in
their own files and can be replaced (Picovoice Porcupine for wake, faster-whisper
or the Whisper API for STT, ElevenLabs for TTS) without touching anything else.

Rule of thumb: if you find yourself importing ``vosk`` or ``pyttsx3`` anywhere
outside a ``*_vosk.py`` / ``*_pyttsx3.py`` implementation file, something has
leaked and the abstraction is broken.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class WakeResult:
    """Outcome of one wake-listening pass.

    ``trailing_command`` holds any words spoken in the same breath *after* the
    wake word, e.g. saying "sumo what time is it" yields
    ``trailing_command="what time is it"``. When the user just says "sumo" and
    pauses, ``trailing_command`` is empty and the caller should acknowledge and
    then listen for a follow-up command.
    """

    detected: bool
    trailing_command: str = ""


class WakeWordDetector(ABC):
    """Continuously listens on a mic stream until the wake word is spoken."""

    @abstractmethod
    def listen_for_wake(self, mic) -> WakeResult:
        """Block on ``mic`` until the wake word is detected, then return.

        ``mic`` is an object exposing ``read(timeout=None) -> bytes`` and
        ``flush()`` (see ``sumo/audio.py``). Implementations must be resilient:
        hearing unrelated speech should not return, it should keep listening.
        """
        raise NotImplementedError


class SpeechToText(ABC):
    """Transcribes a single spoken command after the wake word has fired."""

    @abstractmethod
    def transcribe_command(self, mic) -> str:
        """Capture and transcribe one command utterance from ``mic``.

        Returns the transcript, or an empty string if the user said nothing
        within the configured timeout. Must not block forever.
        """
        raise NotImplementedError


class TextToSpeech(ABC):
    """Speaks text out loud, with a light emotional register hint."""

    @abstractmethod
    def speak(self, text: str, emotion: str = "neutral", intensity: str = "low") -> None:
        """Speak ``text``. ``emotion`` is one of neutral/positive/concerned/urgent
        and ``intensity`` one of low/medium/high; implementations map these to
        whatever expressive controls they have (see the note in the pyttsx3
        implementation about how limited those are)."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Interrupt any in-progress speech and release the audio device."""
        raise NotImplementedError
