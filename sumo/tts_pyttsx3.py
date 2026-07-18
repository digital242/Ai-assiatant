"""pyttsx3-based text-to-speech.

READ THIS BEFORE EXPECTING EMOTIONAL EXPRESSIVENESS FROM v1
-----------------------------------------------------------
pyttsx3 exposes exactly two knobs: ``rate`` (words per minute) and ``volume``
(0.0-1.0). That is the ENTIRE toolkit. It has no control over pitch contour,
prosody, timbre, inflection, or vocal warmth.

The emotion mapping below nudges rate/volume by small amounts so a "positive"
line comes out a touch brighter and quicker and a "concerned" line a touch
slower and calmer. Be honest about what that actually sounds like: it is the
same flat synthetic voice going slightly faster or slower. It will NOT sound
emotionally expressive. The emotional range of Sumo in v1 lives almost entirely
in Claude's word choice, not in the voice.

If genuine vocal warmth/inflection matters to you, the real lever is a neural
TTS with a style/emotion control -- ElevenLabs being the obvious upgrade. Write
an ``ElevenLabsTextToSpeech`` implementing ``TextToSpeech`` and swap it in
``sumo/app.py``; the rest of the app is unaffected. Do not try to compensate by
cranking these rate/volume swings -- exaggerated changes sound worse and more
robotic, not more human, which is why the deltas here are deliberately small.
"""

from __future__ import annotations

from typing import Optional

import pyttsx3

from .interfaces import TextToSpeech
from .logging_setup import EventLogger


class Pyttsx3TextToSpeech(TextToSpeech):
    # Small, conservative deltas as a fraction of the base rate, and small
    # absolute volume offsets. Kept intentionally modest -- see module docstring.
    _RATE_DELTA = {"neutral": 0.0, "positive": 0.06, "concerned": -0.08, "urgent": 0.10}
    _VOLUME_DELTA = {"neutral": 0.0, "positive": 0.04, "concerned": -0.03, "urgent": 0.05}
    _INTENSITY_SCALE = {"low": 0.6, "medium": 1.0, "high": 1.4}

    def __init__(
        self,
        base_rate: int = 175,
        base_volume: float = 0.9,
        voice: Optional[str] = None,
        logger: Optional[EventLogger] = None,
    ):
        self._base_rate = base_rate
        self._base_volume = base_volume
        self._voice = voice
        self._log = logger
        self._engine = None
        self._init_engine()

    def _init_engine(self) -> None:
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", self._base_rate)
        self._engine.setProperty("volume", self._base_volume)
        if self._voice:
            self._engine.setProperty("voice", self._voice)

    def speak(self, text: str, emotion: str = "neutral", intensity: str = "low") -> None:
        if not text or not text.strip():
            return

        scale = self._INTENSITY_SCALE.get(intensity, 1.0)
        rate = self._base_rate * (1 + self._RATE_DELTA.get(emotion, 0.0) * scale)
        volume = self._base_volume + self._VOLUME_DELTA.get(emotion, 0.0) * scale
        volume = max(0.0, min(1.0, volume))

        try:
            self._engine.setProperty("rate", int(rate))
            self._engine.setProperty("volume", volume)
            self._engine.say(text)
            self._engine.runAndWait()
        except RuntimeError:
            # pyttsx3's run loop can wedge if a previous runAndWait was
            # interrupted. Rebuild the engine once and retry rather than dying.
            if self._log:
                self._log.warn("tts_recover", "reinitializing engine")
            self._init_engine()
            self._engine.setProperty("rate", int(rate))
            self._engine.setProperty("volume", volume)
            self._engine.say(text)
            self._engine.runAndWait()

    def stop(self) -> None:
        try:
            if self._engine is not None:
                self._engine.stop()
        except Exception:
            pass
