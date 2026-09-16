"""Launcher for Sumo WITH the on-screen red HUD.

    python run_hud.py

Same voice assistant as run.py, plus a heads-up display window showing Sumo's
state, a live mic meter, the conversation transcript, and a clock. Close the
window (or press Esc) to quit.

For a terminal-only run with no window, use run.py instead.
"""

from sumo.app import run_hud

if __name__ == "__main__":
    run_hud()
