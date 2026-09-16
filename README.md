# Sumo — local voice assistant (Phase 1)

Sumo is a local, wake-word-activated voice assistant. You say **"sumo"**, it
wakes up, you speak a request, and it answers out loud using Claude as the
reasoning engine. It runs persistently on your laptop/PC and works on both
Windows and macOS.

**Phase 1** (this repo) is a fully conversational voice assistant: it listens,
thinks, and talks. It has **no** access to your email, calendar, files, or the
internet — and it says so plainly when you ask for something it can't do. Tool
access (Gmail, Calendar, Drive) is **Phase 2**, deliberately gated and not built
yet.

The pipeline:

```
mic → wake word (Vosk, offline) → speech-to-text (Vosk) → Claude (claude-sonnet-5) → text-to-speech (pyttsx3) → speaker
```

Everything except the Claude call runs offline and free. While idle, Sumo makes
**zero** cloud calls and costs nothing — it only talks to the API once you've
woken it and spoken a command.

---

## About the voice and "emotion"

Sumo's persona shifts register with context — understated warmth for a win,
calm steadiness for a problem, plain and efficient for routine stuff — and most
of that lives in **word choice**, which works well.

You can pick one of two voices with `tts_backend` in `config.yaml`:

- **`pyttsx3`** (default) — offline and free. It offers only two controls:
  speaking rate and volume. Sumo nudges them slightly from the emotion signal
  Claude returns, but be clear on what that sounds like: **the same flat
  synthetic voice going a little faster or slower.** Not real vocal warmth or
  inflection — no idle cost, no cloud, no per-word charge.
- **`fish`** — [Fish Audio](https://fish.audio), a neural voice that actually
  carries warmth and inflection. This is the expressive upgrade. Tradeoffs:
  it's a **paid** API call per reply, and the **reply text is sent to Fish
  Audio's servers** to be synthesized. (Your microphone audio never leaves the
  machine — only the words Sumo is about to say.) Set `FISH_AUDIO_API_KEY` and
  `tts_backend: "fish"`. If Fish is ever unreachable, Sumo automatically falls
  back to the offline voice so it never goes mute.

The TTS layer sits behind a swappable interface, so other engines (e.g.
ElevenLabs) can be dropped in the same way — see
[Swapping components](#swapping-components-later).

## Three ways to run

Same assistant, different front end — pick per launch:

| Command | What you get |
| --- | --- |
| `python run.py` | Terminal only, no window. |
| `python run_hud.py` | Lightweight **Tkinter** desktop window: state ring, mic meter, transcript, clock. Flat vector look (no glow), but tiny and instant. |
| `python run_web.py` | **Browser HUD** — the cinematic one: a glowing red reactor with blur/gradients that reacts to state and your voice, telemetry panels, and a live transcript. Opens in your browser at `http://127.0.0.1:8760`. |

All three drive the exact same voice pipeline; the front end is a swappable
layer. The browser HUD runs a tiny **localhost** web server (bound to
`127.0.0.1`, so it's not exposed to your network) and the page polls it a few
times a second for state — no cloud, no external services.

Tkinter HUD notes: drag it by the title strip; close it (or press Esc) to quit;
tweak `hud_frameless` / `hud_topmost` in `config.yaml`. It uses Tkinter, which
ships with the standard Python installer on Windows and macOS (on some Linux
distros: `sudo apt install python3-tk`).

Browser HUD notes: quit it with **Ctrl+C in the terminal**; settings are
`web_port` / `web_open_browser` in `config.yaml`. If the browser doesn't open
automatically, visit the printed URL yourself.

---

## Requirements

- **Python 3.9+** (3.10 or newer recommended)
- A working **microphone** and **speakers**
- An **Anthropic API key** (`ANTHROPIC_API_KEY`)
- The **Vosk small English model** (~40 MB, downloaded once — see below)

---

## Setup

The steps are the same on both platforms; the platform-specific notes are called
out inline.

### 1. Get the code and create a virtual environment

**macOS / Linux:**
```bash
cd Ai-assiatant
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
cd Ai-assiatant
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

The right TTS backend for your OS is pulled in automatically (`pyobjc` on macOS,
`comtypes` + `pywin32` on Windows).

> **Linux note:** if `sounddevice` can't find PortAudio, install it with your
> package manager (e.g. `sudo apt install portaudio19-dev`), and `pyttsx3` uses
> `espeak` (`sudo apt install espeak`).

### 3. Download the Vosk model

Sumo expects the model at `models/vosk-model-small-en-us-0.15` (this path is set
in `config.yaml` as `vosk_model_path`).

**Easiest — one command** (works on Windows and macOS, no extra tools):
```bash
python setup_model.py
```
This downloads the model (~40 MB), unzips it into `models/`, fixes the folder
layout, and verifies it. Safe to re-run. If it can't reach the internet, use the
manual method below.

**Manual method:**

1. Go to <https://alphacephei.com/vosk/models>
2. Download **`vosk-model-small-en-us-0.15`**
3. Unzip it and place the resulting folder inside `models/` so the final path is:

```
Ai-assiatant/
└── models/
    └── vosk-model-small-en-us-0.15/
        ├── am/
        ├── conf/
        ├── graph/
        └── ...
```

Quick one-liner (macOS/Linux, requires `curl` + `unzip`):
```bash
curl -L -o /tmp/vosk.zip https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip /tmp/vosk.zip -d models/
```

If the folder is missing, Sumo tells you exactly this on startup rather than
crashing with a file-not-found.

### 4. Set your API key

Sumo reads `ANTHROPIC_API_KEY` from the environment. It is never hardcoded,
logged, or printed. Pick one of:

**Option A — shell environment:**
```bash
# macOS/Linux
export ANTHROPIC_API_KEY=sk-ant-...

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

**Option B — a `.env` file** (git-ignored):
```bash
cp .env.example .env
# then edit .env and paste your key
```

### 5. macOS microphone permission

The first time Sumo tries to use the mic, macOS should prompt you to allow it.
If it doesn't (or you denied it), grant it manually:

**System Settings → Privacy & Security → Microphone**, and enable the app that
runs Sumo — your **Terminal** (or iTerm), or the Python binary if you launch it
another way. You may need to restart the terminal after granting.

On **Windows**, if the mic seems dead, check **Settings → Privacy & security →
Microphone** and make sure desktop apps are allowed to use it.

---

## First run

From the project root, with your virtualenv active and key set:

```bash
python run.py
```

You should see:

```
[Sumo] Ready. Say "sumo" to wake me. Press Ctrl+C to quit.
```

Then try it two ways:

- **Two-step:** say **"sumo"**, wait for the short acknowledgment ("Yeah?"),
  then say your request ("what time is it").
- **One breath:** say **"sumo what time is it"** all at once.

Press **Ctrl+C** to quit cleanly.

> **Tip:** "sumo" is a real English word, which is why it works as a phrase
> spotter in Vosk. Speak it clearly. This is not a dedicated wake-word engine, so
> it won't be perfect — that's a deliberate tradeoff for zero idle cost. You can
> upgrade to Picovoice Porcupine later (see below).

---

## Configuration

All non-secret settings live in **`config.yaml`** — you never have to edit Python
to change them. The most useful ones:

| Setting | Meaning |
| --- | --- |
| `wake_word` | The word Sumo listens for (default `sumo`). |
| `claude_model` | The model (default `claude-sonnet-5`). |
| `history_window` | Conversation turns kept in memory (default 12). Resets on restart. |
| `silence_timeout` | Seconds to wait for you to start speaking after the wake word. |
| `tts_rate` / `tts_volume` | Base speaking rate and volume. |
| `input_device` | `null` for the default mic, or a device id (`python -m sounddevice` lists them). |
| `log_conversation` | **Privacy:** `false` by default. Set `true` only to log what was actually said. |

---

## Running it in the background / at startup

### macOS (launchd)

An agent file is provided at `scripts/com.sumo.assistant.plist`.

1. Edit it and replace the three `CHANGE_ME` paths (python in your venv, `run.py`,
   working directory) and your API key.
2. Install and start it:
   ```bash
   cp scripts/com.sumo.assistant.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.sumo.assistant.plist
   ```
3. To stop/uninstall:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.sumo.assistant.plist
   ```

Logs from the launchd process go to `/tmp/sumo.out.log` and `/tmp/sumo.err.log`.
Note: mic permission under launchd can be finicky — if Sumo can't hear you, grant
mic access to the running process in System Settings as above.

### Windows (Startup folder, no console window)

Use `pythonw.exe` so no terminal window appears, via
`scripts/run_sumo_windows.pyw`.

1. Press **Win + R**, type `shell:startup`, press Enter. This opens your Startup
   folder.
2. Create a shortcut in that folder whose **Target** is (adjust the paths):
   ```
   C:\path\to\Ai-assiatant\.venv\Scripts\pythonw.exe C:\path\to\Ai-assiatant\scripts\run_sumo_windows.pyw
   ```
3. Set **Start in** to `C:\path\to\Ai-assiatant`.

Sumo now starts silently at login. Make sure `ANTHROPIC_API_KEY` is available to
that session — either set it as a **User environment variable** (Settings →
System → About → Advanced system settings → Environment Variables) or keep it in
the project `.env`.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `ANTHROPIC_API_KEY is not set` | Set the key (step 4). It's read from the env/`.env` only. |
| `Vosk model folder not found` | Download and place the model (step 3). |
| `Couldn't open the microphone` | Check the mic is connected and permission is granted (step 5). |
| Sumo never wakes | Speak "sumo" clearly; check the right mic is selected (`input_device`); watch `logs/sumo.log` for `wake_miss` entries. |
| Voice sounds robotic/flat | Expected for `pyttsx3`. See [About the voice](#about-the-voice-and-emotion). |
| It "hears itself" | Sumo flushes the mic before listening; use headphones or lower `tts_volume` if echo is bad. |

Errors are written to `logs/sumo.log` (rotating). API and network failures are
logged there and Sumo says a short honest line out loud instead of crashing.

---

## Swapping components later

Every pipeline stage sits behind an interface in `sumo/interfaces.py`. To
upgrade, write a new class implementing the same interface and change **one line**
in `sumo/app.py` (`_build_components`). Nothing else in the app needs to change.

| Stage | v1 implementation | Alternatives |
| --- | --- | --- |
| Wake word | `VoskWakeWordDetector` | Picovoice Porcupine |
| Speech-to-text | `VoskSpeechToText` | faster-whisper / Whisper API |
| Text-to-speech | `Pyttsx3TextToSpeech` | `FishAudioTextToSpeech` (built in), ElevenLabs |
| Display | `NullUI` (headless) | `TkinterHUD` + `WebHUD` (both built in) |

---

## Project layout

```
Ai-assiatant/
├── run.py                 # launcher (terminal only): python run.py
├── run_hud.py             # launcher with the Tkinter HUD window
├── run_web.py             # launcher with the browser HUD
├── setup_model.py         # one-command Vosk model installer
├── config.yaml            # all non-secret settings
├── .env.example           # template for the API keys
├── requirements.txt
├── README.md
├── TESTING.md             # re-runnable Phase 1 test checklist
├── sumo/
│   ├── app.py             # startup checks + resilient loop + both entry points
│   ├── config.py          # config.yaml loading
│   ├── logging_setup.py   # rotating file logging
│   ├── audio.py           # shared microphone stream (+ live level for the meter)
│   ├── interfaces.py      # WakeWordDetector / SpeechToText / TextToSpeech ABCs
│   ├── ui.py              # AssistantUI interface + NullUI (headless)
│   ├── hud_tk.py          # TkinterHUD red heads-up display (desktop window)
│   ├── web_hud.py         # WebHUD localhost server for the browser HUD
│   ├── web/index.html     # the cinematic browser HUD page (canvas + CSS glow)
│   ├── vosk_shared.py     # cached Vosk model loader
│   ├── wake_vosk.py       # Vosk wake-word detector
│   ├── stt_vosk.py        # Vosk speech-to-text
│   ├── tts_pyttsx3.py     # pyttsx3 text-to-speech (offline, + emotion mapping)
│   ├── tts_fish.py        # Fish Audio text-to-speech (neural, optional)
│   ├── persona.py         # Sumo's system prompt
│   └── brain.py           # Claude wrapper (forced structured reply)
├── scripts/
│   ├── com.sumo.assistant.plist   # macOS launchd agent
│   └── run_sumo_windows.pyw       # Windows no-console launcher
├── models/                # place the Vosk model here
└── logs/                  # rotating logs land here
```

---

## Phase 2 — not built yet (gated)

Phase 2 adds real tool-calling so Sumo can *do* things: read/search Gmail, read
Google Calendar, read Google Drive files you point it at. This is intentionally
**not** built until Phase 1 is confirmed working, and each tool will be confirmed
before it's built. Any action with a real-world side effect (sending email,
creating an event, modifying a file) will require **explicit spoken confirmation**
before it runs. Read-only actions won't.
