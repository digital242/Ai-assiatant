"""Launcher for Sumo. Run with:  python run.py

This is a thin wrapper around ``sumo.app.run`` so you can start the assistant
without remembering the module path, and so the Windows ``pythonw.exe`` /
macOS ``launchd`` setups in the README have a single stable entry point.
"""

from sumo.app import run

if __name__ == "__main__":
    run()
