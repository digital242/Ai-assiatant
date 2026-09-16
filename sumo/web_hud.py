"""Browser-based heads-up display for Sumo.

Unlike the Tkinter HUD, a web page can do real glow, blur, gradients and smooth
animation -- the cinematic red-HUD look. This module is only the plumbing: a
tiny localhost HTTP server (standard library, no web framework) that serves the
HUD page and a ``/state`` JSON endpoint the page polls a few times a second for
the current state, transcript and mic level. All the visuals live in
``web/index.html``.

The server binds to 127.0.0.1 by default, so it is reachable only from this
machine, not the network. It runs on a daemon thread; the voice loop runs on the
main thread (no GUI main-thread constraint like Tkinter has), so ``run_web`` is
structured just like the headless run.
"""

from __future__ import annotations

import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from .logging_setup import EventLogger
from .ui import STATE_IDLE, AssistantUI

HTML_PATH = os.path.join(os.path.dirname(__file__), "web", "index.html")
_MAX_TRANSCRIPT = 12


class WebHUD(AssistantUI):
    def __init__(
        self,
        mic,
        wake_word: str = "sumo",
        host: str = "127.0.0.1",
        port: int = 8760,
        open_browser: bool = True,
        logger: Optional[EventLogger] = None,
    ):
        self._mic = mic
        self._wake_word = wake_word
        self._host = host
        self._port = port
        self._logger = logger

        self._lock = threading.Lock()
        self._state = STATE_IDLE
        self._transcript = []  # list of {seq, speaker, text, emotion}
        self._seq = 0
        self._notice = ""

        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._start_server(open_browser)

    # -- AssistantUI ------------------------------------------------------
    def set_state(self, state: str) -> None:
        with self._lock:
            self._state = state

    def add_user(self, text: str) -> None:
        self._append("you", text, "neutral")

    def add_sumo(self, text: str, emotion: str = "neutral") -> None:
        self._append("sumo", text, emotion)

    def notify(self, message: str) -> None:
        with self._lock:
            self._notice = message

    def _append(self, speaker: str, text: str, emotion: str) -> None:
        with self._lock:
            self._seq += 1
            self._transcript.append(
                {"seq": self._seq, "speaker": speaker, "text": text, "emotion": emotion}
            )
            if len(self._transcript) > _MAX_TRANSCRIPT:
                self._transcript = self._transcript[-_MAX_TRANSCRIPT:]

    def _snapshot(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "level": round(self._mic.level(), 4),
                "transcript": list(self._transcript),
                "notice": self._notice,
                "wake_word": self._wake_word,
            }

    # -- server -----------------------------------------------------------
    def _start_server(self, open_browser: bool) -> None:
        hud = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence default request logging
                pass

            def do_GET(self):  # noqa: N802 (name fixed by BaseHTTPRequestHandler)
                if self.path in ("/", "/index.html"):
                    self._send_html()
                elif self.path.startswith("/state"):
                    self._send_state()
                else:
                    self.send_error(404)

            def _send_html(self):
                try:
                    with open(HTML_PATH, "rb") as fh:
                        body = fh.read()
                except OSError:
                    self.send_error(500, "HUD page not found")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_state(self):
                body = json.dumps(hud._snapshot()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer((self._host, self._port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        url = f"http://{self._host}:{self._port}/"
        if self._logger:
            self._logger.event("web_hud", f"serving {url}")
        print(f"[Sumo] HUD running at {url}")
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass  # headless / no browser -- the URL is printed above

    def shutdown(self) -> None:
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            finally:
                self._server = None
