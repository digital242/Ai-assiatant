"""Vosk-based speech-to-text for the actual command (after the wake word).

Same engine as the wake detector in v1, on purpose -- one dependency, one model.
To upgrade accuracy on domain vocabulary (FRP, IS 1726, distributor/product
names) swap in a ``FasterWhisperSpeechToText`` or ``WhisperApiSpeechToText``
implementing ``SpeechToText``; the app changes one line.

Capture behaviour:
  * Wait up to ``silence_timeout`` seconds for the user to START speaking. If
    they never do, return "" and the caller goes back to idle listening.
  * Once they are speaking, capture until Vosk finalizes the utterance on a
    natural pause, or until ``max_command_seconds`` as a hard safety cap so a
    stuck stream can never hang the loop.
"""

from __future__ import annotations

import json
import queue
import time

from vosk import KaldiRecognizer

from .interfaces import SpeechToText
from .logging_setup import EventLogger
from .vosk_shared import get_model


class VoskSpeechToText(SpeechToText):
    def __init__(
        self,
        model_path: str,
        sample_rate: int,
        silence_timeout: float,
        max_command_seconds: float,
        logger: EventLogger,
    ):
        self._recognizer = KaldiRecognizer(get_model(model_path), sample_rate)
        self._silence_timeout = silence_timeout
        self._max_command_seconds = max_command_seconds
        self._log = logger

    def transcribe_command(self, mic) -> str:
        self._recognizer.Reset()
        mic.flush()
        start = time.monotonic()
        speaking = False

        while True:
            try:
                data = mic.read(timeout=0.5)
            except queue.Empty:
                data = None

            now = time.monotonic()

            if data is not None:
                if self._recognizer.AcceptWaveform(data):
                    text = json.loads(self._recognizer.Result()).get("text", "").strip()
                    if text:
                        self._log.event("command_captured", f"words={len(text.split())}")
                        return text
                    # Empty final result = a silence chunk; keep waiting.
                else:
                    partial = json.loads(self._recognizer.PartialResult()).get("partial", "").strip()
                    if partial:
                        speaking = True

            if not speaking and (now - start) > self._silence_timeout:
                self._log.event("command_timeout", "no_speech")
                return ""

            if speaking and (now - start) > self._max_command_seconds:
                text = json.loads(self._recognizer.FinalResult()).get("text", "").strip()
                self._log.event("command_capped", f"words={len(text.split())}")
                return text
