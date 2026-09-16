# Sumo — Phase 1 testing checklist

Re-run this after any change. These are manual, because the whole point is the
end-to-end voice loop with a real mic and speaker. Check each box.

Setup for testing:
- Virtualenv active, `pip install -r requirements.txt` done.
- Vosk model in place at `models/vosk-model-small-en-us-0.15`.
- A quiet-ish room and working mic + speakers (headphones reduce echo).

---

## A. Startup / precondition failures (should be clear, never a crash)

- [ ] **No API key → clear error, not a crash.**
  Unset the key and start Sumo. It should print a clear message telling you to
  set `ANTHROPIC_API_KEY` and exit — **not** a stack trace, and **not** a crash
  partway into listening.
  ```bash
  # macOS/Linux
  unset ANTHROPIC_API_KEY
  python run.py        # expect the clear "ANTHROPIC_API_KEY is not set" message
  ```

- [ ] **Missing Vosk model → clear setup pointer.**
  Temporarily rename the model folder and start Sumo. Expect a message pointing
  at the download link and `config.yaml`, not a raw file-not-found.

- [ ] **Microphone unavailable / permission denied → clear fix instructions.**
  On macOS, deny mic permission (System Settings → Privacy & Security →
  Microphone) and start Sumo. Expect a clear message telling you to grant mic
  access, not a stack trace. (Re-grant afterward.)

---

## B. Wake + command flow

- [ ] **Two-step: "sumo" alone, then a pause, gets a short acknowledgment and
  waits for the follow-up.**
  Say **"sumo"** and stop. Sumo should say a brief acknowledgment ("Yeah?",
  "Go ahead.", etc.) and then listen. Then say **"what time is it"** — it should
  answer.

- [ ] **One breath: "sumo what time is it" works too.**
  Say the whole thing in one go. Sumo should skip the acknowledgment and answer
  directly.

- [ ] **Nothing after wake → graceful.**
  Say "sumo", get the acknowledgment, then stay silent. After the timeout Sumo
  should say "I didn't catch that." and quietly go back to idle listening — not
  hang.

---

## C. Emotional register (contextual, not a constant layer)

The point here is that tone tracks content — and that routine stuff stays plain.

- [ ] **Positive update reads noticeably warmer.**
  Say: **"sumo, the deploy succeeded."** The reply should carry understated
  warmth ("nice, that clears it" energy) — not exclamation spam, but clearly not
  flat.

- [ ] **Negative update reads calm and steady, clearly different from the win.**
  Say: **"sumo, the connection failed three times in a row."** The reply should
  be calm, direct, steady — and audibly a *different register* from the positive
  case, not the same flat sentence with words swapped.

- [ ] **Routine, low-stakes exchange stays plain — no injected enthusiasm.**
  Say: **"sumo, what time is it."** The answer should be short and plain. If it
  sounds artificially peppy, the persona is over-coloring and that's a fail.

> Note: because v1 uses `pyttsx3`, the *voice* difference between these is only a
> small rate/volume nudge — most of the register lives in the **words**. Judge
> this test mainly on word choice and tone of phrasing, not on vocal warmth,
> which `pyttsx3` can't produce. (See README, "About the voice".)

---

## D. Resilience

- [ ] **Killing the process mid-response doesn't hang or lock the audio device.**
  While Sumo is speaking a reply, press **Ctrl+C**. It should shut down cleanly.
  Immediately start it again with `python run.py` — the mic/speaker should be
  available, no "device busy" error.

- [ ] **A single failed exchange doesn't kill the loop.**
  Simulate an API failure (e.g. temporarily set a bogus `ANTHROPIC_API_KEY`
  *after* startup is not possible, so instead pull your network connection),
  then wake Sumo and ask something. It should say a short honest line
  ("I couldn't reach the API right now.") and **keep listening** — restore the
  network and the next request should work without restarting.

---

## E. Logging & privacy

- [ ] **Conversation content is NOT logged by default.**
  With `log_conversation: false` (the default), have a short conversation, then
  open `logs/sumo.log`. You should see events like `wake_detected`,
  `command_captured`, `exchange | tone=...` — but **not** the actual words you
  said or Sumo's replies.

- [ ] **Debug logging can be turned on deliberately.**
  Set `log_conversation: true` in `config.yaml`, restart, have an exchange, and
  confirm the transcript now appears in the log. Set it back to `false` when
  done.

- [ ] **The API key never appears in the log or console**, in normal or debug
  mode. Grep the log to be sure:
  ```bash
  grep -i "sk-ant" logs/sumo.log   # expect no matches
  ```

---

## F. Tkinter HUD window (optional — only if you use `python run_hud.py`)

- [ ] **HUD opens and shows the ring, mic meter, clock, and transcript panel.**
  Launch `python run_hud.py`. A red-on-black window appears with a central ring
  labelled IDLE.

- [ ] **The ring changes with state.** Say "sumo …" and watch the center label
  move through LISTENING → THINKING → SPEAKING → IDLE as Sumo handles the turn.

- [ ] **The mic meter reacts to your voice.** The ring of small bars around the
  circle should grow/brighten as you speak and settle when you're quiet.

- [ ] **The transcript shows both sides.** Your command appears under YOU and
  Sumo's reply under SUMO.

- [ ] **The window drags and closes.** Drag it by the top title strip; close it
  with the ✕ (top-right) or Esc. Closing it shuts Sumo down cleanly — re-running
  `python run_hud.py` or `python run.py` works with no leftover audio lock.

## G. Browser HUD (optional — only if you use `python run_web.py`)

- [ ] **The HUD page opens.** Run `python run_web.py`. Your browser opens
  `http://127.0.0.1:8760` showing a glowing red reactor, telemetry panels, a
  clock, and a transcript panel. (If it doesn't auto-open, visit the URL printed
  in the terminal.)

- [ ] **The reactor reacts to state.** Say "sumo …" and watch the center label
  and reactor animation move through IDLE → LISTENING → THINKING → SPEAKING.

- [ ] **The radial meter reacts to your voice.** The ring of bars grows/brightens
  as you speak and settles when quiet.

- [ ] **The transcript updates live** with YOU and SUMO lines, newest first-in
  at the bottom.

- [ ] **It's local-only.** The page is served from `127.0.0.1` — confirm it's not
  reachable from another device on your network (that's intended).

- [ ] **Ctrl+C in the terminal quits cleanly** and the port is free on the next
  run (no "address already in use").

## H. Fish Audio voice (optional — only if you set `tts_backend: "fish"`)

- [ ] **The neural voice plays.** With `FISH_AUDIO_API_KEY` set and
  `tts_backend: "fish"` in `config.yaml`, ask Sumo something and confirm the
  reply is spoken in the Fish Audio voice (clearly richer than the offline one).

- [ ] **Fallback keeps Sumo audible.** Temporarily break the Fish key (or pull
  the network) and ask again. Sumo should still speak — it falls back to the
  offline voice — and log `fish_error`, not go silent or crash.

- [ ] **The Fish key never appears in the log.**
  ```bash
  grep -i "fish" logs/sumo.log        # events like fish_error are fine
  grep -iE "sk-fish|Bearer" logs/sumo.log   # expect NO matches (no key leaked)
  ```

## Done when

All boxes above are checked on at least one target OS. Once you've confirmed
Phase 1 works, tell me and we'll start Phase 2 (tool access) — one tool at a
time, with spoken confirmation gating any real-world action.
