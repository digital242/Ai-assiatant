"""The brain: Claude as the reasoning engine.

Uses the official ``anthropic`` SDK. The model returns a structured reply via a
forced tool call (``respond``) so we reliably get the spoken text plus an
emotion/intensity hint in one round trip -- rather than trying to infer sentiment
after the fact. Conversation history is kept in memory, trimmed to a window, and
reset on restart (no persistence in Phase 1, by design).

The API key comes from the ``ANTHROPIC_API_KEY`` environment variable, which the
SDK reads on its own. It is never stored here, never logged, never printed.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from anthropic import (
    Anthropic,
    APIConnectionError,
    APIError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)

from .logging_setup import EventLogger
from .persona import build_system_prompt

# Structured-output contract. Forcing this tool guarantees we always get a
# well-formed reply + emotion + intensity, no fragile JSON-in-text parsing.
RESPOND_TOOL = {
    "name": "respond",
    "description": (
        "Return Sumo's spoken reply and the emotional register it should be "
        "delivered in. This is the only way to reply to the user."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reply": {
                "type": "string",
                "description": (
                    "The spoken response. Plain text only -- no markdown, "
                    "bullets, or emoji. One to three sentences unless more "
                    "detail was explicitly requested."
                ),
            },
            "emotion": {
                "type": "string",
                "enum": ["neutral", "positive", "concerned", "urgent"],
                "description": "Genuine register of the reply. Default neutral.",
            },
            "intensity": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "How strongly the emotion applies. Default low.",
            },
        },
        "required": ["reply", "emotion", "intensity"],
    },
}


class BrainError(Exception):
    """Raised when Claude can't be reached / errors out. The app catches this,
    says something short and honest out loud, and keeps listening."""


class ClaudeBrain:
    def __init__(
        self,
        model: str,
        history_window: int,
        max_tokens: int,
        logger: EventLogger,
        log_conversation: bool = False,
    ):
        # Anthropic() reads ANTHROPIC_API_KEY from the environment itself.
        self._client = Anthropic()
        self._model = model
        self._history_window = history_window
        self._max_tokens = max_tokens
        self._log = logger
        self._log_conversation = log_conversation
        self._history: List[dict] = []

    def think(self, user_text: str) -> Tuple[str, str, str]:
        """Send ``user_text`` to Claude and return (reply, emotion, intensity)."""
        self._history.append({"role": "user", "content": user_text})

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=build_system_prompt(),
                messages=self._history,
                tools=[RESPOND_TOOL],
                tool_choice={"type": "tool", "name": "respond"},
            )
        except (
            APIConnectionError,
            RateLimitError,
            AuthenticationError,
            APIStatusError,
            APIError,
        ) as exc:
            # Don't keep a user turn we never answered -- it would poison the
            # next request's history.
            self._history.pop()
            self._log.error("api_error", type(exc).__name__)
            raise BrainError(str(exc)) from exc

        reply, emotion, intensity = self._parse(response)
        self._history.append({"role": "assistant", "content": reply})
        self._trim_history()

        if self._log_conversation:
            self._log.event(
                "exchange",
                f"user={user_text!r} reply={reply!r} tone={emotion}/{intensity}",
            )
        else:
            self._log.event("exchange", f"tone={emotion}/{intensity}")

        return reply, emotion, intensity

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _parse(response) -> Tuple[str, str, str]:
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "respond":
                data = block.input or {}
                reply = (data.get("reply") or "").strip()
                emotion = data.get("emotion") or "neutral"
                intensity = data.get("intensity") or "low"
                if reply:
                    return reply, emotion, intensity
        # Defensive fallback: forced tool use should always yield the block, but
        # if something unexpected happens, salvage any plain text.
        for block in response.content:
            if getattr(block, "type", None) == "text" and block.text.strip():
                return block.text.strip(), "neutral", "low"
        return "I got a response I couldn't read. Try again.", "concerned", "low"

    def _trim_history(self) -> None:
        # Keep the last N turns (a turn = a user/assistant pair).
        max_messages = self._history_window * 2
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]
        # History must begin with a user message for the API.
        while self._history and self._history[0]["role"] != "user":
            self._history.pop(0)
