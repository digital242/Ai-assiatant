"""Launcher for Sumo WITH the browser-based HUD (the cinematic one).

    python run_web.py

Starts the voice assistant and a local HUD web page (default
http://127.0.0.1:8760), opening it in your browser. The page shows a glowing
red reactor that reacts to Sumo's state and your voice, plus a live transcript.
Press Ctrl+C in the terminal to quit.

Other launchers:
    python run.py       -- terminal only, no window
    python run_hud.py   -- lightweight Tkinter desktop window
"""

from sumo.app import run_web

if __name__ == "__main__":
    run_web()
