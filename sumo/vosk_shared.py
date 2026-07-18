"""Shared Vosk model loader.

Both the wake-word detector and the speech-to-text stage use Vosk in v1. Loading
the acoustic model is the expensive part (memory + a second or two of startup),
so we cache it here and hand the same in-memory ``Model`` to both. This keeps the
two implementations decoupled at the interface level while avoiding a redundant
second copy of the model in RAM.
"""

from __future__ import annotations

import functools
import os

from vosk import Model, SetLogLevel


class VoskModelMissingError(Exception):
    """The configured Vosk model folder doesn't exist. Turned into a clear
    setup-pointing message by the app, not a raw FileNotFoundError."""


# Silence Vosk/Kaldi's very chatty stderr logging. -1 = quiet.
SetLogLevel(-1)


@functools.lru_cache(maxsize=4)
def get_model(model_path: str) -> Model:
    if not os.path.isdir(model_path):
        raise VoskModelMissingError(model_path)
    return Model(model_path)
