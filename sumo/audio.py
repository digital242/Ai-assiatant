"""Microphone capture.

A single ``MicStream`` is opened once at startup and shared by the wake-word
detector and the speech-to-text stage. Both read 16 kHz / mono / int16 frames
from the same queue-backed stream. Opening the device exactly once (rather than
per-listen) is deliberate: it avoids the device-lock / "audio busy" problems you
hit when repeatedly opening and closing the input on some platforms.
"""

from __future__ import annotations

import queue
from typing import Optional

import sounddevice as sd


class MicUnavailableError(Exception):
    """Raised when the microphone can't be opened -- no device, or the OS denied
    permission. The app turns this into a clear, actionable console message."""


class MicStream:
    def __init__(
        self,
        sample_rate: int = 16000,
        block_size: int = 8000,
        device: Optional[int] = None,
    ):
        self._sample_rate = sample_rate
        self._block_size = block_size
        self._device = device
        self._queue: "queue.Queue[bytes]" = queue.Queue()
        self._stream: Optional[sd.RawInputStream] = None

    # -- lifecycle ---------------------------------------------------------
    def open(self) -> None:
        try:
            self._stream = sd.RawInputStream(
                samplerate=self._sample_rate,
                blocksize=self._block_size,
                device=self._device,
                dtype="int16",
                channels=1,
                callback=self._callback,
            )
            self._stream.start()
        except Exception as exc:  # sounddevice raises PortAudioError and others
            raise MicUnavailableError(str(exc)) from exc

    def close(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None

    def __enter__(self) -> "MicStream":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # -- reading -----------------------------------------------------------
    def _callback(self, indata, frames, time_info, status) -> None:
        # ``status`` flags overflows etc.; we don't hard-fail on them.
        self._queue.put(bytes(indata))

    def read(self, timeout: Optional[float] = None) -> bytes:
        """Return the next audio frame. Blocks until one is available (or until
        ``timeout`` seconds elapse, raising ``queue.Empty``)."""
        return self._queue.get(timeout=timeout)

    def flush(self) -> None:
        """Drop any buffered audio. Called before we start a fresh listen so we
        don't transcribe stale frames (including Sumo's own spoken prompt echo)."""
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
