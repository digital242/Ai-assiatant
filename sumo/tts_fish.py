"""Fish Audio text-to-speech -- an expressive neural voice for Sumo.

This is the upgrade over pyttsx3: a real neural TTS whose voice actually carries
warmth and inflection, not just a rate/volume tweak. It implements the same
``TextToSpeech`` interface, so selecting it is a config change and nothing in the
main loop is aware of the difference.

Two tradeoffs to be honest about, both different from the offline pyttsx3 path:
  * Cost: each spoken reply is a paid API call to Fish Audio.
  * Privacy: the reply TEXT is sent to Fish Audio's servers to be synthesized.
    (Your microphone audio still never leaves the machine -- only the words Sumo
    is about to say are sent, not anything you said.)

The API key is read from the FISH_AUDIO_API_KEY environment variable only. It is
never hardcoded, logged, or printed.

Playback: we ask Fish for a WAV stream, parse it with the standard-library
``wave`` module, and play the raw PCM through sounddevice -- no extra audio codec
dependency. If anything about the Fish call or playback fails, we fall back to
the offline pyttsx3 voice so Sumo never goes mute mid-conversation.
"""

from __future__ import annotations

import io
import os
import wave
from typing import Optional

import requests
import sounddevice as sd

from .interfaces import TextToSpeech
from .logging_setup import EventLogger

FISH_TTS_URL = "https://api.fish.audio/v1/tts"


class FishConfigError(Exception):
    """Fish Audio is selected but not usable (missing API key)."""


class FishAudioTextToSpeech(TextToSpeech):
    # Neural voices carry most of the emotion themselves, so we nudge only speed,
    # and only slightly. Volume is left to Fish's loudness normalization.
    _SPEED_DELTA = {"neutral": 0.0, "positive": 0.05, "concerned": -0.07, "urgent": 0.08}
    _INTENSITY_SCALE = {"low": 0.6, "medium": 1.0, "high": 1.4}

    def __init__(
        self,
        voice_id: Optional[str] = None,
        model: str = "s1",
        base_speed: float = 1.0,
        sample_rate: int = 44100,
        timeout: float = 30.0,
        api_key_env: str = "FISH_AUDIO_API_KEY",
        logger: Optional[EventLogger] = None,
        fallback: Optional[TextToSpeech] = None,
    ):
        self._api_key = os.environ.get(api_key_env)
        if not self._api_key:
            raise FishConfigError(
                f"{api_key_env} is not set; cannot use the Fish Audio voice."
            )
        self._voice_id = voice_id
        self._model = model
        self._base_speed = base_speed
        self._sample_rate = sample_rate
        self._timeout = timeout
        self._log = logger
        self._fallback = fallback
        self._out_stream: Optional[sd.RawOutputStream] = None

    def speak(self, text: str, emotion: str = "neutral", intensity: str = "low") -> None:
        if not text or not text.strip():
            return
        try:
            wav_bytes = self._synthesize(text, emotion, intensity)
            self._play_wav(wav_bytes)
        except Exception as exc:  # noqa: BLE001 -- never let TTS crash the loop
            if self._log:
                self._log.error("fish_error", type(exc).__name__)
            if self._fallback is not None:
                # Keep Sumo audible: fall back to the offline voice.
                self._fallback.speak(text, emotion=emotion, intensity=intensity)

    def _synthesize(self, text: str, emotion: str, intensity: str) -> bytes:
        scale = self._INTENSITY_SCALE.get(intensity, 1.0)
        speed = self._base_speed * (1 + self._SPEED_DELTA.get(emotion, 0.0) * scale)
        payload = {
            "text": text,
            "format": "wav",
            "sample_rate": self._sample_rate,
            "prosody": {"speed": round(speed, 3), "volume": 0},
            "normalize": True,
            "latency": "normal",
        }
        if self._voice_id:
            payload["reference_id"] = self._voice_id

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._model:
            # Selects the synthesis backbone (e.g. "s1", "speech-1.5").
            headers["model"] = self._model

        response = requests.post(
            FISH_TTS_URL, json=payload, headers=headers, timeout=self._timeout
        )
        response.raise_for_status()
        return response.content

    def _play_wav(self, wav_bytes: bytes) -> None:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frame_rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())

        dtype = {1: "int8", 2: "int16", 4: "int32"}.get(sample_width, "int16")
        self._out_stream = sd.RawOutputStream(
            samplerate=frame_rate, channels=channels, dtype=dtype
        )
        try:
            self._out_stream.start()
            self._out_stream.write(frames)
        finally:
            try:
                self._out_stream.stop()
                self._out_stream.close()
            finally:
                self._out_stream = None

    def stop(self) -> None:
        if self._out_stream is not None:
            try:
                self._out_stream.abort()
                self._out_stream.close()
            except Exception:
                pass
            finally:
                self._out_stream = None
        if self._fallback is not None:
            self._fallback.stop()
