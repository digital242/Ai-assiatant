"""Sumo -- local, wake-word-activated voice assistant. Phase 1 entry points.

Pipeline:  mic -> wake word (Vosk) -> speech-to-text (Vosk) -> Claude -> TTS.

Two ways to run:
  * ``run()``      -- headless / terminal only (NullUI). This is what ``run.py``
                      calls, and the loop runs on the main thread.
  * ``run_hud()``  -- with the on-screen red HUD. Tk owns the main thread, so the
                      voice loop runs on a worker thread and reports state to the
                      HUD through the AssistantUI interface. This is what
                      ``run_hud.py`` calls.

Both share the same startup checks and the same ``_listen_loop``; the only
difference is which UI is attached and which thread the loop runs on.
"""

from __future__ import annotations

import os
import random
import sys
import threading

from .audio import MicStream, MicUnavailableError
from .brain import BrainError, ClaudeBrain
from .config import load_config
from .interfaces import SpeechToText, TextToSpeech, WakeWordDetector
from .logging_setup import setup_logging
from .stt_vosk import VoskSpeechToText
from .tts_pyttsx3 import Pyttsx3TextToSpeech
from .ui import (
    STATE_IDLE,
    STATE_LISTENING,
    STATE_SPEAKING,
    STATE_THINKING,
    AssistantUI,
    NullUI,
)
from .vosk_shared import VoskModelMissingError
from .wake_vosk import VoskWakeWordDetector

# Short, neutral acknowledgments for the two-step case ("sumo" ... then command).
_ACKS = ["Yeah?", "Go ahead.", "Listening.", "What's up?", "Mm-hm?"]


def _load_env_file() -> None:
    """Populate the environment from a local .env for the API keys' sake (the
    Anthropic key, and the Fish Audio key if used). Non-secret settings still
    come from config.yaml -- .env only holds secrets."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _fatal(message: str) -> None:
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
    """Construct wake / STT / brain. TTS is built inside the loop (in the worker
    thread) so backends with thread affinity behave. Wake/STT/TTS are referenced
    only through their interfaces, so swapping an implementation is a one-line
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
            "  Install it the easy way:  python setup_model.py\n"
            "  Or download vosk-model-small-en-us-0.15 from\n"
            "    https://alphacephei.com/vosk/models\n"
            "  and place it to match 'vosk_model_path' in config.yaml."
        )

    brain = ClaudeBrain(
        model=config.claude_model,
        history_window=config.history_window,
        max_tokens=config.max_tokens,
        logger=logger,
        log_conversation=config.log_conversation,
    )
    return wake, stt, brain


def _build_tts(config, logger) -> TextToSpeech:
    """Select the TTS backend from config. The offline pyttsx3 voice always
    exists; when 'fish' is chosen it wraps pyttsx3 as an automatic fallback so a
    Fish Audio outage never leaves Sumo mute."""
    offline = Pyttsx3TextToSpeech(
        base_rate=config.tts_rate,
        base_volume=config.tts_volume,
        voice=config.tts_voice,
        logger=logger,
    )
    if config.tts_backend == "fish":
        from .tts_fish import FishAudioTextToSpeech, FishConfigError

        try:
            return FishAudioTextToSpeech(
                voice_id=config.fish_voice_id,
                model=config.fish_model,
                base_speed=config.fish_speed,
                sample_rate=config.fish_sample_rate,
                logger=logger,
                fallback=offline,
            )
        except FishConfigError as exc:
            logger.error("fish_config", type(exc).__name__)
            print(f"[Sumo] Fish Audio voice not available ({exc}); using offline voice.")
            return offline
    return offline


def _listen_loop(config, logger, wake, stt, brain, mic, ui: AssistantUI, stop_event) -> None:
    """The core exchange loop. Resilient: one failed exchange logs and recovers.
    Runs on the main thread (headless) or a worker thread (HUD)."""
    tts = _build_tts(config, logger)
    ui.set_state(STATE_IDLE)
    print(f"[Sumo] Ready. Say \"{config.wake_word}\" to wake me.")
    try:
        while not stop_event.is_set():
            try:
                result = wake.listen_for_wake(mic)
                if not result.detected:
                    continue

                if result.trailing_command:
                    command = result.trailing_command  # one-breath case
                else:
                    ui.set_state(STATE_LISTENING)
                    tts.speak(random.choice(_ACKS), emotion="neutral", intensity="low")
                    command = stt.transcribe_command(mic)

                if not command.strip():
                    ui.set_state(STATE_IDLE)
                    tts.speak("I didn't catch that.", emotion="neutral", intensity="low")
                    continue

                ui.add_user(command)
                ui.set_state(STATE_THINKING)
                try:
                    reply, emotion, intensity = brain.think(command)
                except BrainError:
                    ui.notify("Couldn't reach the API")
                    ui.set_state(STATE_IDLE)
                    tts.speak("I couldn't reach the API right now.",
                              emotion="concerned", intensity="low")
                    continue

                ui.add_sumo(reply, emotion)
                ui.set_state(STATE_SPEAKING)
                tts.speak(reply, emotion=emotion, intensity=intensity)
                ui.set_state(STATE_IDLE)

            except KeyboardInterrupt:
                raise
            except Exception as exc:  # noqa: BLE001 -- loop must survive anything
                logger.error("loop_recover", type(exc).__name__)
                ui.set_state(STATE_IDLE)
                continue
    except KeyboardInterrupt:
        print("\n[Sumo] Shutting down.")
    finally:
        logger.event("shutdown", "")
        tts.stop()


def _startup(config_path: str = "config.yaml"):
    """Shared startup: env, config, logging, precondition checks, components,
    and an opened mic. Returns everything the loop needs."""
    _load_env_file()
    config = load_config(config_path)
    logger = setup_logging(
        config.log_path,
        level=config.log_level,
        max_bytes=config.log_max_bytes,
        backups=config.log_backups,
    )

    _check_api_key()
    wake, stt, brain = _build_components(config, logger)

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
            "  Microphone. On Windows: Settings -> Privacy & security -> Microphone."
        )

    logger.event("startup", f"wake_word={config.wake_word!r} model={config.claude_model} "
                            f"tts={config.tts_backend}")
    return config, logger, wake, stt, brain, mic


def run() -> None:
    """Headless / terminal run."""
    config, logger, wake, stt, brain, mic = _startup()
    ui = NullUI()
    stop_event = threading.Event()
    try:
        _listen_loop(config, logger, wake, stt, brain, mic, ui, stop_event)
    finally:
        mic.close()


def run_hud() -> None:
    """Run with the on-screen red HUD."""
    config, logger, wake, stt, brain, mic = _startup()

    try:
        from .hud_tk import TkinterHUD
    except Exception as exc:  # tkinter missing / no display
        _fatal(
            "Couldn't start the HUD window.\n"
            f"  Details: {exc}\n"
            "  Make sure you're on a desktop session with a display. You can\n"
            "  always run without the HUD:  python run.py"
        )

    ui = TkinterHUD(
        mic=mic,
        wake_word=config.wake_word,
        frameless=config.hud_frameless,
        topmost=config.hud_topmost,
    )
    stop_event = threading.Event()
    ui.on_closed(stop_event.set)

    worker = threading.Thread(
        target=_listen_loop,
        args=(config, logger, wake, stt, brain, mic, ui, stop_event),
        daemon=True,
    )
    worker.start()
    try:
        ui.mainloop()  # blocks on the main thread until the window is closed
    finally:
        stop_event.set()
        mic.close()


if __name__ == "__main__":
    run()
