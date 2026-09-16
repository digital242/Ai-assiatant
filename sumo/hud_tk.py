"""Tkinter heads-up display for Sumo.

A frameless red-on-black HUD: a central ring that changes as Sumo idles,
listens, thinks and speaks; a radial meter around it driven by live mic level; a
running clock; and a transcript of the conversation. It's an original design in a
sci-fi HUD aesthetic -- not a copy of any wallpaper, and with no branding.

Threading: Tk must own the main thread, so ``mainloop()`` runs there while the
voice loop runs on a worker thread. The worker only ever calls the AssistantUI
methods, which just drop events on a thread-safe queue; the on-screen widgets are
touched exclusively by the main-thread ``_tick`` animation loop that drains that
queue. Nothing else is shared.

Tkinter ships with Python, so there is no extra dependency here.
"""

from __future__ import annotations

import math
import queue
import time
import tkinter as tk
from collections import deque
from typing import Optional

from .ui import (
    STATE_IDLE,
    STATE_LISTENING,
    STATE_SPEAKING,
    STATE_THINKING,
    AssistantUI,
)

# -- palette (red on near-black) ---------------------------------------------
BG = "#080809"
RED_DIM = "#5a1414"
RED_MID = "#b81f1f"
RED = "#ff2b2b"
RED_BRIGHT = "#ff6b6b"
GREY = "#40161a"
USER_COLOR = "#ff8a5c"   # amber-ish for the user's words
SUMO_COLOR = "#ff4d4d"
TEXT_COLOR = "#ffd0d0"
FAINT = "#7a2a2a"


def _hex_to_rgb(c: str):
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def _mix(c1: str, c2: str, t: float) -> str:
    """Linear blend between two hex colors; t in 0..1."""
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


class TkinterHUD(AssistantUI):
    def __init__(
        self,
        mic,
        wake_word: str = "sumo",
        frameless: bool = True,
        topmost: bool = True,
        width: int = 560,
        height: int = 680,
    ):
        self._mic = mic
        self._wake_word = wake_word.upper()
        self._w = width
        self._h = height

        self._events: "queue.Queue[tuple]" = queue.Queue()
        self._state = STATE_IDLE
        self._transcript = deque(maxlen=8)  # (speaker, text, emotion)
        self._script_dirty = True
        self._notice = ""
        self._notice_until = 0.0

        self._phase = 0.0   # breathing/pulse phase
        self._spin = 0.0    # thinking arc rotation

        # -- window ----------------------------------------------------------
        self._root = tk.Tk()
        self._root.title("SUMO")
        self._root.configure(bg=BG)
        if frameless:
            self._root.overrideredirect(True)
        if topmost:
            self._root.attributes("-topmost", True)
        self._center_window()

        self._canvas = tk.Canvas(
            self._root, width=width, height=height, bg=BG, highlightthickness=0
        )
        self._canvas.pack(fill="both", expand=True)

        self._draw_static()
        self._bind_controls(frameless)

        self._cx = width // 2
        self._cy = 250
        self._ring_r = 110

    # -- AssistantUI (called from the worker thread) ----------------------
    def set_state(self, state: str) -> None:
        self._events.put(("state", state))

    def add_user(self, text: str) -> None:
        self._events.put(("user", text))

    def add_sumo(self, text: str, emotion: str = "neutral") -> None:
        self._events.put(("sumo", (text, emotion)))

    def notify(self, message: str) -> None:
        self._events.put(("notify", message))

    # -- lifecycle --------------------------------------------------------
    def mainloop(self) -> None:
        self._tick()
        self._root.mainloop()

    def on_closed(self, callback) -> None:
        """Register a callback fired when the window closes (so the app can stop
        the voice loop and clean up)."""
        self._on_closed = callback

    # -- window helpers ---------------------------------------------------
    def _center_window(self) -> None:
        self._root.update_idletasks()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = (sw - self._w) // 2
        y = max(20, (sh - self._h) // 3)
        self._root.geometry(f"{self._w}x{self._h}+{x}+{y}")

    def _bind_controls(self, frameless: bool) -> None:
        self._root.bind("<Escape>", self._close)
        self._canvas.tag_bind("close", "<Button-1>", self._close)
        # Drag the window by its title strip.
        self._canvas.tag_bind("titlebar", "<Button-1>", self._start_move)
        self._canvas.tag_bind("titlebar", "<B1-Motion>", self._on_move)
        if not frameless:
            self._root.protocol("WM_DELETE_WINDOW", self._close)

    def _start_move(self, event) -> None:
        self._drag_x = event.x_root
        self._drag_y = event.y_root
        self._win_x = self._root.winfo_x()
        self._win_y = self._root.winfo_y()

    def _on_move(self, event) -> None:
        dx = event.x_root - self._drag_x
        dy = event.y_root - self._drag_y
        self._root.geometry(f"+{self._win_x + dx}+{self._win_y + dy}")

    def _close(self, event=None) -> None:
        cb = getattr(self, "_on_closed", None)
        if cb is not None:
            try:
                cb()
            except Exception:
                pass
        try:
            self._root.destroy()
        except Exception:
            pass

    # -- drawing ----------------------------------------------------------
    def _draw_static(self) -> None:
        w = self._w
        c = self._canvas
        # outer border frame
        c.create_rectangle(6, 6, w - 6, self._h - 6, outline=GREY, width=1)
        c.create_rectangle(10, 10, w - 10, self._h - 10, outline=RED_DIM, width=1)
        # title strip (draggable). A wide invisible-ish rect carries the binding.
        c.create_rectangle(10, 10, w - 10, 52, outline="", fill=BG, tags="titlebar")
        c.create_line(10, 52, w - 10, 52, fill=RED_DIM, width=1)
        c.create_text(
            28, 30, anchor="w", text=" ".join(self._wake_word),
            fill=RED, font=("Courier New", 20, "bold"), tags="titlebar",
        )
        c.create_text(
            28, 46, anchor="w", text="voice assistant",
            fill=FAINT, font=("Courier New", 8, "bold"), tags="titlebar",
        )
        # close glyph
        c.create_text(
            w - 26, 30, text="✕", fill=RED_MID,
            font=("Courier New", 16, "bold"), tags="close",
        )
        # transcript divider
        c.create_line(30, 428, w - 30, 428, fill=RED_DIM, width=1)
        c.create_text(
            34, 418, anchor="w", text="TRANSCRIPT",
            fill=FAINT, font=("Courier New", 8, "bold"),
        )
        # footer hint
        c.create_text(
            w // 2, self._h - 22,
            text=f'say "{self._wake_word.lower()}" to wake     •     esc to close',
            fill=FAINT, font=("Courier New", 9),
        )

    def _tick(self) -> None:
        try:
            self._drain_events()
            self._phase += 0.12
            if self._state == STATE_THINKING:
                self._spin = (self._spin + 9) % 360
            self._redraw_dynamic()
            if self._script_dirty:
                self._redraw_transcript()
                self._script_dirty = False
        except tk.TclError:
            return  # window went away mid-tick; stop cleanly
        self._root.after(40, self._tick)

    def _drain_events(self) -> None:
        while True:
            try:
                kind, payload = self._events.get_nowait()
            except queue.Empty:
                break
            if kind == "state":
                self._state = payload
            elif kind == "user":
                self._transcript.append(("you", payload, "neutral"))
                self._script_dirty = True
            elif kind == "sumo":
                text, emotion = payload
                self._transcript.append(("sumo", text, emotion))
                self._script_dirty = True
            elif kind == "notify":
                self._notice = payload
                self._notice_until = time.monotonic() + 6.0

    def _redraw_dynamic(self) -> None:
        c = self._canvas
        c.delete("dyn")
        cx, cy, r = self._cx, self._cy, self._ring_r
        breathe = (math.sin(self._phase) + 1) / 2  # 0..1

        # state-specific ring appearance
        if self._state == STATE_IDLE:
            ring_color = _mix(RED_DIM, RED_MID, breathe * 0.6)
            label, sub = "IDLE", f'SAY "{self._wake_word}"'
            width = 3
        elif self._state == STATE_LISTENING:
            ring_color = _mix(RED_MID, RED_BRIGHT, 0.4 + 0.6 * self._mic.level())
            label, sub = "LISTENING", "go ahead"
            width = 4
        elif self._state == STATE_THINKING:
            ring_color = RED
            label, sub = "THINKING", "· · ·"
            width = 3
        else:  # speaking
            fast = (math.sin(self._phase * 2.2) + 1) / 2
            ring_color = _mix(RED_MID, RED_BRIGHT, fast)
            label, sub = "SPEAKING", ""
            width = 3 + int(2 * fast)

        # base ring
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=ring_color, width=width, tags="dyn")
        c.create_oval(cx - r + 14, cy - r + 14, cx + r - 14, cy + r - 14,
                      outline=_mix(BG, ring_color, 0.5), width=1, tags="dyn")

        # thinking: a bright sweeping arc
        if self._state == STATE_THINKING:
            c.create_arc(cx - r, cy - r, cx + r, cy + r, start=self._spin, extent=100,
                         style="arc", outline=RED_BRIGHT, width=4, tags="dyn")

        # radial mic meter around the ring
        self._draw_meter(cx, cy, r + 12)

        # center labels
        c.create_text(cx, cy - 8, text=label, fill=RED_BRIGHT,
                      font=("Courier New", 22, "bold"), tags="dyn")
        if sub:
            c.create_text(cx, cy + 18, text=sub, fill=FAINT,
                          font=("Courier New", 10), tags="dyn")

        # clock (top-right, redrawn each tick)
        c.create_text(self._w - 46, 30, anchor="e", text=time.strftime("%H:%M:%S"),
                      fill=RED_MID, font=("Courier New", 13, "bold"), tags="dyn")

        # transient notice
        if self._notice and time.monotonic() < self._notice_until:
            c.create_text(cx, 392, text=self._notice, fill=RED_BRIGHT,
                          font=("Courier New", 10, "bold"), tags="dyn")

    def _draw_meter(self, cx: int, cy: int, radius: int) -> None:
        c = self._canvas
        level = self._mic.level()
        n = 60
        for i in range(n):
            frac = i / n
            ang = 2 * math.pi * frac - math.pi / 2
            lit = frac <= level
            length = 10 if lit else 5
            col = _mix(RED_MID, RED_BRIGHT, min(1.0, level * 1.3)) if lit else GREY
            x1 = cx + radius * math.cos(ang)
            y1 = cy + radius * math.sin(ang)
            x2 = cx + (radius + length) * math.cos(ang)
            y2 = cy + (radius + length) * math.sin(ang)
            c.create_line(x1, y1, x2, y2, fill=col, width=2, tags="dyn")

    def _redraw_transcript(self) -> None:
        c = self._canvas
        c.delete("script")
        y = 442
        entries = list(self._transcript)
        for speaker, text, _emotion in entries:
            if y > self._h - 46:
                break
            label_color = USER_COLOR if speaker == "you" else SUMO_COLOR
            c.create_text(36, y, anchor="nw", text=speaker.upper(), fill=label_color,
                          font=("Courier New", 9, "bold"), tags="script")
            tid = c.create_text(96, y, anchor="nw", width=self._w - 130, text=text,
                                fill=TEXT_COLOR, font=("Courier New", 11), tags="script")
            bbox = c.bbox(tid)
            h = (bbox[3] - bbox[1]) if bbox else 16
            y += max(18, h) + 8
