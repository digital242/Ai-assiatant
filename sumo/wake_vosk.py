"""Vosk-based wake-word detector.

This is a phrase spotter, not a dedicated wake-word engine. We run continuous
offline transcription and watch for the wake word ("sumo") in each finalized
utterance. This is a deliberate cost/reliability tradeoff: zero cloud calls and
zero per-listen cost while idle, at the price of accuracy compared to something
like Picovoice Porcupine.

To swap in Porcupine later: write a ``PorcupineWakeWordDetector`` implementing
``WakeWordDetector`` and change one line in ``sumo/app.py``. Nothing else in the
app knows or cares which detector is in use.

Detection strategy: we key off *finalized* utterances (Vosk finalizes on a short
silence). That naturally handles both required cases:
  * "sumo" then a pause  -> utterance is just "sumo", trailing command empty,
    caller acknowledges and listens for the follow-up.
  * "sumo what time is it" in one breath -> utterance is the whole phrase,
    trailing command is "what time is it", caller skips the acknowledgment.
"""

from __future__ import annotations

import json

from vosk import KaldiRecognizer

from .interfaces import WakeResult, WakeWordDetector
from .logging_setup import EventLogger
from .vosk_shared import get_model


class VoskWakeWordDetector(WakeWordDetector):
    def __init__(
        self,
        model_path: str,
        sample_rate: int,
        wake_word: str,
        logger: EventLogger,
    ):
        self._recognizer = KaldiRecognizer(get_model(model_path), sample_rate)
        self._wake_word = wake_word.strip().lower()
        self._log = logger

    def listen_for_wake(self, mic) -> WakeResult:
        self._recognizer.Reset()
        mic.flush()
        while True:
            data = mic.read()
            if not self._recognizer.AcceptWaveform(data):
                continue
            text = json.loads(self._recognizer.Result()).get("text", "").strip().lower()
            if not text:
                continue
            if self._contains_wake(text):
                trailing = self._extract_trailing(text)
                self._log.event(
                    "wake_detected",
                    f"one_shot={'yes' if trailing else 'no'}",
                )
                return WakeResult(detected=True, trailing_command=trailing)
            # Heard speech, but no wake word -- keep idling.
            self._log.event("wake_miss", "speech_without_wake_word")

    # -- helpers -----------------------------------------------------------
    def _contains_wake(self, text: str) -> bool:
        words = text.split()
        return self._wake_word in words or any(
            w.startswith(self._wake_word) for w in words
        )

    def _extract_trailing(self, text: str) -> str:
        """Return everything spoken after the first occurrence of the wake word."""
        words = text.split()
        for i, word in enumerate(words):
            if word == self._wake_word or word.startswith(self._wake_word):
                return " ".join(words[i + 1:]).strip()
        return ""
