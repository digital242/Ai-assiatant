@echo off
REM ============================================================================
REM  Sumo voice assistant - one-click launcher for Windows.
REM
REM  Just double-click this file. It will:
REM    1. download the project (only the first time, needs Git),
REM    2. set up its Python environment and dependencies (first time only),
REM    3. install the speech model (first time only),
REM    4. ask for your Anthropic API key once and remember it in a .env file,
REM    5. start Sumo with the browser HUD.
REM
REM  You can save this file anywhere (e.g. your Desktop). Requires Python and
REM  Git to be installed.
REM ============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo(
echo   ============================
echo      SUMO VOICE ASSISTANT
echo   ============================
echo(

REM --- 1. Make sure we have the project ---------------------------------------
if not exist "run_web.py" (
    if exist "Ai-assiatant\run_web.py" (
        REM Already downloaded on a previous run; just step into it.
        cd Ai-assiatant
    ) else (
        where git >nul 2>&1
        if errorlevel 1 (
            echo [X] Git is not installed, so I can't download the project.
            echo     Install Git from https://git-scm.com/download/win  then run this again.
            echo     ^(Or download the project ZIP from GitHub and put this file inside it.^)
            goto :halt
        )
        echo [*] Downloading Sumo for the first time...
        git clone https://github.com/digital242/Ai-assiatant.git
        if errorlevel 1 goto :halt
        cd Ai-assiatant
        git checkout claude/sumo-voice-assistant-gnxuex
    )
)

REM --- 2. Pick a Python launcher ----------------------------------------------
set "PY=py"
where py >nul 2>&1 || set "PY=python"
where %PY% >nul 2>&1
if errorlevel 1 (
    echo [X] Python is not installed. Get it from https://www.python.org/downloads/
    echo     During install, tick "Add Python to PATH". Then run this again.
    goto :halt
)

REM --- 3. Create the virtual environment (first time only) --------------------
if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating the Python environment...
    %PY% -m venv .venv
    if errorlevel 1 goto :halt
)
call ".venv\Scripts\activate.bat"

REM --- 4. Install dependencies (first time only) ------------------------------
if not exist ".venv\.deps_installed" (
    echo [*] Installing dependencies... this can take a couple of minutes.
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 goto :halt
    echo done> ".venv\.deps_installed"
)

REM --- 5. Install the speech model (skips if already there) -------------------
echo [*] Checking the speech model...
python setup_model.py
if errorlevel 1 goto :halt

REM --- 6. Anthropic API key ----------------------------------------------------
if "%ANTHROPIC_API_KEY%"=="" (
    if not exist ".env" (
        echo(
        echo [*] I need your Anthropic API key ^(it starts with sk-ant-^).
        set /p "KEY=    Paste it here and press Enter: "
        (echo ANTHROPIC_API_KEY=!KEY!)> ".env"
        echo [*] Saved. You won't be asked again.
    )
)

REM --- 7. Launch ---------------------------------------------------------------
echo(
echo [*] Starting Sumo. A browser window will open with the HUD.
echo     Say "sumo" to wake it. Close this window to quit.
echo(
python run_web.py

:halt
echo(
pause
endlocal
