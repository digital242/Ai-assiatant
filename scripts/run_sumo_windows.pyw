"""Windows background launcher for Sumo (no console window).

Run this with pythonw.exe (not python.exe) so no terminal window appears:

    pythonw.exe run_sumo_windows.pyw

To start Sumo automatically at login, put a shortcut to this file (run with
pythonw.exe) in your Startup folder. Press Win+R, type  shell:startup , Enter,
then create a shortcut in that folder whose target is, for example:

    C:\\path\\to\\Ai-assiatant\\.venv\\Scripts\\pythonw.exe  C:\\path\\to\\Ai-assiatant\\scripts\\run_sumo_windows.pyw

See the README Windows section for step-by-step instructions.
"""

import os
import sys

# Make sure we run from the project root so config.yaml / models / logs resolve.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from sumo.app import run  # noqa: E402

if __name__ == "__main__":
    run()
