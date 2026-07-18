"""Sumo -- local, wake-word-activated voice assistant. Phase 1 entry point.

Pipeline:  mic -> wake word (Vosk) -> speech-to-text (Vosk) -> Claude -> TTS.

The startup checks fail loud and clear (not with stack traces) for the three
things most likely to be wrong on a fresh machine: no API key, missing Vosk
model, unavailable microphone. After that, the listen loop is resilient -- one
failed exchange logs and recovers instead of killing the background process.
"""

from __future__ import annotations

import os
import random
import sys

from .audio import MicStream, MicUnavailableError
from .brain import BrainError, ClaudeBrain
from .config import load_config
from .interfaces import SpeechToText, TextToSpeech, WakeWordDetector
from .logging_setup import setup_logging
from .stt_vosk import VoskSpeechToText
from .tts_pyttsx3 import Pyttsx3TextToSpeech
from .vosk_shared import VoskModelMissingError
from .wake_vosk import VoskWakeWordDetector

# Short, neutral acknowledgments for the two-step case ("sumo" ... then command).
_ACKS = ["Yeah?", "Go ahead.", "Listening.", "What's up?", "Mm-hm?"]


def _load_env_file() -> None:
    """Optionally populate the environment from a local .env for the API key's
    sake. Non-secret settings still come from config.yaml -- .env only exists as
    a convenience for the one secret."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _fatal(message: str) -> None:
    """Print a clear, actionable error to the console and exit non-zero. Used for
    the startup preconditions, deliberately not raising a traceback."""
    print(f"\n[Sumo] {message}\n", file=sys.stderr)
    sys.exit(1)


def _check_api_key() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        _fatal(
            "ANTHROPIC_API_KEY is not set.\n"
            "  Set it before starting Sumo:\n"
            "    macOS/Linux:  export ANTHROPIC_API_KEY=sk-ant-...\n"
            "    Windows (PowerShell):  $env:ANTHROPIC_API_KEY=\"sk-ant-...\"\n"
            "  Or put it in a .env file next to config.yaml (see .env.example)."
        )


def _build_components(config, logger):
    """Construct the pipeline. Wake/STT/TTS are referenced only through their
    interfaces below this point, so swapping an implementation is a one-line
    change right here."""
    try:
        wake: WakeWordDetector = VoskWakeWordDetector(
            model_path=config.vosk_model_path,
            sample_rate=config.sample_rate,
            wake_word=config.wake_word,
            logger=logger,
        )
        stt: SpeechToText = VoskSpeechToText(
            model_path=config.vosk_model_path,
            sample_rate=config.sample_rate,
            silence_timeout=config.silence_timeout,
            max_command_seconds=config.max_command_seconds,
            logger=logger,
        )
    except VoskModelMissingError as exc:
        _fatal(
            f"Vosk model folder not found at: {exc}\n"
            "  Download vosk-model-small-en-us-0.15 from\n"
            "    https://alphacephei.com/vosk/models\n"
            "  unzip it, and place it so the folder matches 'vosk_model_path' in\n"
            "  config.yaml. See the README 'Vosk model' section for exact steps."
        )

    tts: TextToSpeech = Pyttsx3TextToSpeech(
        base_rate=config.tts_rate,
        base_volume=config.tts_volume,
        voice=config.tts_voice,
        logger=logger,
    )
    brain = ClaudeBrain(
        model=config.claude_model,
        history_window=config.history_window,
        max_tokens=config.max_tokens,
        logger=logger,
        log_conversation=config.log_conversation,
    )
    return wake, stt, tts, brain


def _handle_exchange(command, brain, tts, logger) -> None:
    """One full turn: command text -> Claude -> spoken reply. Errors here are
    caught by the caller; API errors specifically get a short honest voice reply."""
    try:
        reply, emotion, intensity = brain.think(command)
    except BrainError:
        # Already logged inside the brain. Say something short and honest.
        tts.speak("I couldn't reach the API right now.", emotion="concerned", intensity="low")
        return
    tts.speak(reply, emotion=emotion, intensity=intensity)


def run() -> None:
    _load_env_file()
    config = load_config()
    logger = setup_logging(
        config.log_path,
        level=config.log_level,
        max_bytes=config.log_max_bytes,
        backups=config.log_backups,
    )

    _check_api_key()
    wake, stt, tts, brain = _build_components(config, logger)

    # Open the mic once and share it. A failure here is almost always a missing
    # device or an OS permission denial -- say exactly that.
    mic = MicStream(
        sample_rate=config.sample_rate,
        block_size=config.block_size,
        device=config.input_device,
    )
    try:
        mic.open()
    except MicUnavailableError as exc:
        _fatal(
            "Couldn't open the microphone.\n"
            f"  Details: {exc}\n"
            "  Check that a microphone is connected and that this app has mic\n"
            "  permission. On macOS: System Settings -> Privacy & Security ->\n"
            "  Microphone, and enable your terminal (or the app running Sumo).\n"
            "  On Windows: Settings -> Privacy & security -> Microphone."
        )

    logger.event("startup", f"wake_word={config.wake_word!r} model={config.claude_model}")
    print(f"[Sumo] Ready. Say \"{config.wake_word}\" to wake me. Press Ctrl+C to quit.")

    try:
        while True:
            try:
                result = wake.listen_for_wake(mic)
                if not result.detected:
                    continue

                if result.trailing_command:
                    # One-breath case: "sumo what time is it".
                    command = result.trailing_command
                else:
                    # Two-step case: acknowledge, then listen for the command.
                    tts.speak(random.choice(_ACKS), emotion="neutral", intensity="low")
                    command = stt.transcribe_command(mic)

                if not command.strip():
                    tts.speak("I didn't catch that.", emotion="neutral", intensity="low")
                    continue

                _handle_exchange(command, brain, tts, logger)

            except KeyboardInterrupt:
                raise
            except Exception as exc:  # noqa: BLE001 -- loop must survive anything
                # One bad exchange must not kill the background process.
                logger.error("loop_recover", type(exc).__name__)
                continue
    except KeyboardInterrupt:
        print("\n[Sumo] Shutting down.")
    finally:
        logger.event("shutdown", "")
        tts.stop()
        mic.close()


if __name__ == "__main__":
    run()
