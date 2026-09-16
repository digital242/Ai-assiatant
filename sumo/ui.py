"""UI abstraction for Sumo.

The listen loop reports what it's doing through this interface -- state changes,
what you said, what Sumo replied -- without knowing whether anything is actually
on screen. ``NullUI`` is the headless default (terminal-only); ``TkinterHUD`` in
``hud_tk.py`` is the on-screen red heads-up display. Swapping or adding a UI (a
web dashboard, a tray icon) means implementing this interface and nothing else.

Thread note: the voice loop runs on a worker thread and calls these methods.
Implementations must be thread-safe -- the Tk HUD does this by pushing events
onto a queue that its own main-thread animation loop drains, so no widget is ever
touched from the worker thread.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

# The four states the loop moves through. Kept as plain strings so the interface
# has no dependency on any UI toolkit.
STATE_IDLE = "idle"
STATE_LISTENING = "listening"
STATE_THINKING = "thinking"
STATE_SPEAKING = "speaking"


class AssistantUI(ABC):
    @abstractmethod
    def set_state(self, state: str) -> None:
        """Report the current pipeline state (one of the STATE_* constants)."""

    @abstractmethod
    def add_user(self, text: str) -> None:
        """Show a command the user just spoke."""

    @abstractmethod
    def add_sumo(self, text: str, emotion: str = "neutral") -> None:
        """Show a reply Sumo just gave."""

    @abstractmethod
    def notify(self, message: str) -> None:
        """Show a transient status line (e.g. an API error)."""


class NullUI(AssistantUI):
    """No-op UI for headless/terminal runs. Everything still works; nothing is
    drawn. The console prints in app.py carry the user-facing feedback."""

    def set_state(self, state: str) -> None:
        pass

    def add_user(self, text: str) -> None:
        pass

    def add_sumo(self, text: str, emotion: str = "neutral") -> None:
        pass

    def notify(self, message: str) -> None:
        pass
