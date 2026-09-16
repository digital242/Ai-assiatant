"""Configuration loading for Sumo.

Non-secret settings live in ``config.yaml`` so you never have to edit Python to
change the wake word, TTS rate, model name, history window, or timeouts.

The one secret -- ``ANTHROPIC_API_KEY`` -- is deliberately NOT part of this file
or ``config.yaml``. It is read from the environment only (optionally populated
from a local ``.env`` for convenience). It is never stored in config, never
logged, and never printed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import Any, Dict

import yaml

# Defaults. Anything present in config.yaml overrides these.
DEFAULTS: Dict[str, Any] = {
    # Wake / audio
    "wake_word": "sumo",
    "vosk_model_path": "models/vosk-model-small-en-us-0.15",
    "sample_rate": 16000,
    "block_size": 8000,
    "input_device": None,  # None = system default input device
    # Command capture
    "silence_timeout": 6.0,      # seconds to wait for the user to START speaking
    "max_command_seconds": 15.0,  # hard cap once they are speaking
    # Brain (Claude)
    "claude_model": "claude-sonnet-5",
    "history_window": 12,   # conversational turns kept (user+assistant pairs)
    "max_tokens": 400,
    # Text to speech
    "tts_backend": "pyttsx3",  # "pyttsx3" (offline) or "fish" (Fish Audio, neural)
    "tts_rate": 175,     # words per minute (pyttsx3 baseline)
    "tts_volume": 0.9,   # 0.0 - 1.0
    "tts_voice": None,   # platform voice id, None = default
    # Fish Audio (used only when tts_backend == "fish"). Key comes from the
    # FISH_AUDIO_API_KEY env var, never from here.
    "fish_voice_id": None,     # a Fish voice/model reference id, or None for default
    "fish_model": "s1",        # synthesis backbone, e.g. "s1" or "speech-1.5"
    "fish_sample_rate": 44100,
    "fish_speed": 1.0,         # baseline speaking speed multiplier
    # Tkinter heads-up display (used only when launched via run_hud.py)
    "hud_frameless": True,     # borderless HUD window
    "hud_topmost": True,       # keep the HUD above other windows
    # Browser heads-up display (used only when launched via run_web.py)
    "web_host": "127.0.0.1",   # localhost only -- not exposed to the network
    "web_port": 8760,
    "web_open_browser": True,  # auto-open the HUD page on start
    # Logging
    "log_path": "logs/sumo.log",
    "log_level": "INFO",
    "log_max_bytes": 1_000_000,
    "log_backups": 3,
    # Privacy: when False, conversation content is NEVER written to the log.
    # Turn on only for local debugging of what was actually said.
    "log_conversation": False,
}


@dataclass
class Config:
    wake_word: str
    vosk_model_path: str
    sample_rate: int
    block_size: int
    input_device: Any
    silence_timeout: float
    max_command_seconds: float
    claude_model: str
    history_window: int
    max_tokens: int
    tts_backend: str
    tts_rate: int
    tts_volume: float
    tts_voice: Any
    fish_voice_id: Any
    fish_model: str
    fish_sample_rate: int
    fish_speed: float
    hud_frameless: bool
    hud_topmost: bool
    web_host: str
    web_port: int
    web_open_browser: bool
    log_path: str
    log_level: str
    log_max_bytes: int
    log_backups: int
    log_conversation: bool


def load_config(path: str = "config.yaml") -> Config:
    """Load ``config.yaml`` merged over the defaults. Missing file is fine --
    the defaults are used and Sumo still runs."""
    data: Dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
            if isinstance(loaded, dict):
                data = loaded

    merged = {**DEFAULTS, **{k: v for k, v in data.items() if v is not None or k in ("input_device", "tts_voice")}}
    valid = {f.name for f in fields(Config)}
    unknown = set(data) - valid
    if unknown:
        # Not fatal -- just ignore stray keys so a typo in config doesn't crash.
        merged = {k: v for k, v in merged.items() if k in valid}
    return Config(**{k: merged[k] for k in valid})
