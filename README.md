# Claude VoicePlayer

A local voice for Claude Code. When a session finishes a turn, Claude VoicePlayer reads a short summary of the
reply aloud and shows a small floating player. When a reply asks you to choose something, the player shows it
as a **call** with clickable answers, and sends your answer back to that session.

Speech runs on your machine with [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) (ONNX, CPU, about 6x
real time). No API keys and no cloud TTS.

> **Windows only for now.** The player uses Windows APIs (DPI awareness, the taskbar app ID, UI Automation to
> type answers into the Claude desktop app). The TTS core (`tts.py`) also runs on macOS and Linux, but the
> player and the call features are tested on Windows 10/11 only.

Made by [MadeFire AI](https://madefire.ai).

Not affiliated with or endorsed by Anthropic. Claude is a trademark of Anthropic.

---

## Install and setup

### Requirements

| What | Notes |
| --- | --- |
| Windows 10 or 11 | |
| Python 3.10 or newer | [python.org](https://www.python.org/downloads/). Tick "Add to PATH". Tk ships with it |
| Claude Code | The Stop and Notification hooks come from Claude Code (CLI, desktop app, or IDE extension) |
| `claude` CLI (optional) | Used for spoken summaries (`claude -p`) and for answering in the background (`claude --resume -p`). Without it, the player reads a cleaned-up excerpt of each reply |
| About 400 MB of disk | Mostly the Kokoro model files |
| AutoHotkey v2 (optional) | Only for the global "read selected text" hotkey (`kokoro_hotkey.ahk`) |

### 1. Clone

```
git clone https://github.com/yprimakov/claude-voice-player.git
cd claude-voice-player
```

### 2. Run the setup script

```
python setup.py
```

It does five things:

1. Creates a virtual environment in `venv\`.
2. Installs the packages in `requirements.txt` (kokoro-onnx, onnxruntime, sounddevice, soundfile, Pillow).
3. Downloads the Kokoro model files into `models\` from the kokoro-onnx releases: `kokoro-v1.0.onnx`
   (about 311 MB) and `voices-v1.0.bin` (about 27 MB).
4. Writes `kokoro_hook.bat`, the launcher the hooks call.
5. Edits `~\.claude\settings.json`: it adds a **Stop** hook and a **Notification** hook (matcher
   `permission_prompt`) that run `kokoro_hook.bat`. Existing hooks are kept.

### 3. Turn voice on

Voice replies play only while the flag file `~\.claude\voice_enabled` exists:

```
type nul > "%USERPROFILE%\.claude\voice_enabled"
```

Delete the file to turn voice off.

### 4. Start it

You don't need to start anything by hand. The first Stop hook starts the daemon (`voiced.py`, on
`127.0.0.1:4712`, one copy only), and the daemon opens the player. To start it yourself:

```
venv\Scripts\pythonw.exe show_player.pyw
```

`show_player.pyw` also brings back a hidden or minimized player. Pin it to Start or the taskbar if you like.

### 5. Settings

Click the gear in the player. Changes apply at once and are saved to `%LOCALAPPDATA%\local-tts\settings.json`.
Scripts can use `GET /settings` and `POST /settings` with a JSON object of keys to change. The full list is in
[Settings](#settings) below.

### Calls from other tools (push API)

Anything on the same machine can put a call on the player:

```
POST http://127.0.0.1:4712/calls/push
{"id": "my-call-1", "project": "My project", "thread": "Design", "question": "Ship it?",
 "options": ["Yes", "Not yet"], "url": "https://claude.ai/..."}
```

`POST /calls/push/<id>/done` closes it. `GET /calls/answers/next?timeout=600` long-polls for the answer the user
picked. The daemon listens on 127.0.0.1 only and refuses requests from browsers.

### Uninstall

1. Quit the player (right-click, then **Quit voice queue**).
2. Open `~\.claude\settings.json` and remove the Stop and Notification hook entries whose command points at
   `kokoro_hook.bat`.
3. Delete `~\.claude\voice_enabled`.
4. Delete `%LOCALAPPDATA%\local-tts` (history and settings).
5. Delete the cloned folder.

### Troubleshooting

| Problem | What to check |
| --- | --- |
| Nothing speaks | Does `~\.claude\voice_enabled` exist? Is the player muted (M)? Run `doctor.bat` |
| Replies are read word for word, not summarized | The `claude` CLI was not found on PATH. Install Claude Code's CLI, or turn off "Summarize replies" |
| The player is gone | Run `show_player.pyw`, or check the taskbar button "Claude VoicePlayer" |
| Model download failed | Download the two files from the kokoro-onnx releases page into `models\` and run `setup.py` again |
| `onnxruntime` DLL errors | Use plain `onnxruntime`, not `onnxruntime-directml` (it hangs with Kokoro on some AMD systems) |
| A second copy will not start | Only one daemon can run. `curl http://127.0.0.1:4712/state` shows the running one |

Logs and history live in `%LOCALAPPDATA%\local-tts`.

---

## Using the TTS engine directly

Any agent can invoke the TTS engine directly:

```
# Speak text silently (no window, blocks until audio finishes)
venv\Scripts\python.exe tts.py "Your message here" --autoplay

# Show the interactive playback controller
venv\Scripts\python.exe tts.py "Your message here" --play

# Save to WAV file
venv\Scripts\python.exe tts.py "Your message here" --out output.wav
```

---

## Available voices

| ID | Description |
|---|---|
| `af_heart` | American Female — warm, natural *(default)* |
| `af_bella` | American Female — clear, expressive |
| `af_nicole` | American Female — smooth, professional |
| `af_aoede` | American Female — bright, energetic |
| `af_kore` | American Female — calm, authoritative |
| `af_sarah` | American Female — friendly, conversational |
| `af_sky` | American Female — gentle, airy |
| `am_adam` | American Male — strong, clear |
| `am_michael` | American Male — warm, measured |
| `am_echo` | American Male — resonant |
| `am_eric` | American Male — steady, confident |
| `am_fenrir` | American Male — deep, powerful |
| `am_liam` | American Male — youthful, upbeat |
| `am_onyx` | American Male — rich, baritone |
| `am_puck` | American Male — nimble, lively |
| `bf_emma` | British Female — refined, articulate |
| `bf_isabella` | British Female — warm, elegant |
| `bm_george` | British Male — formal, distinguished |
| `bm_lewis` | British Male — casual, approachable |

Change the default voice in `kokoro_hotkey.ahk`:
```ahk
VOICE := "am_adam"
SPEED := "1.1"
```

Or pass `--voice` and `--speed` on the CLI.

---


## Voice queue (voiced.py)

The Stop hook no longer plays audio itself. It posts each reply to one local daemon, `voiced.py`
(127.0.0.1:4712, started by the hook on demand; only one copy can run), which:

- turns each reply into a short spoken summary (`claude -p --model haiku`, hooks off): what was done and what
  you need to do, never code or JSON. `--raw` or `VOICED_SUMMARY=0` speaks a cleaned-up excerpt instead
- speaks one reply at a time, so parallel sessions never talk over each other. A newer reply from a thread
  replaces that thread's older unspoken ones, and replies from different threads are never merged (only
  background runs are), so every call answers back to the thread that asked it. Replies that need a decision
  play before plain status updates; a burst of 3+ background runs from one folder is spoken once with a count
- records headless runs (`claude -p`, SDK, batch prompts) in history without speaking them
  (`--speak-headless` or `VOICED_SPEAK_HEADLESS=1` to speak them too)
- keeps history as text in `%LOCALAPPDATA%\local-tts\history.jsonl` (7 days; replays are synthesized again)
- finds sessions that wait on you even when no Stop hook made a call: every minute it reads the Claude app's
  Code sessions and makes a quiet call (history only, not spoken) for an open AskUserQuestion, with its options,
  or for a turn the app marks as needing you or ready for review. One call per session, its newest question, never twice for the same
  turn, and none when the hook's call is already open. Archived, pytest and temp sessions are skipped. The
  summarizer's own runs keep no transcripts (`--no-session-persistence`)
- also finds plain terminal sessions (`~/.claude/projects` transcripts, interactive `claude` only): an open
  AskUserQuestion, or a final reply the hook never reported that reads like a question (summarized silently).
  Their Open action copies the resume command
- turns permission prompts into "Approve in the app" calls (Notification hook, matcher `permission_prompt`,
  registered by `setup.py`). The call's one button opens the session; approving happens there
- still summarizes replies from muted projects, muted mode and Do Not Disturb, so their questions become silent calls
- closes a found call once its session writes anything newer (answered there, or the agent carried on)

### The player (player.py)

Double-click empty background to open or collapse it (not on buttons, and not after a drag). A floating capsule in the MadeFire style (Outfit, DM Sans, JetBrains Mono, Inter, Space Grotesk and Fraunces
are bundled in `fonts/`, all SIL OFL with their licences, and loaded for this process only; Windows fonts are the
fallback if a file is missing). The ember orb plays and pauses; it breathes, and the card's rim glows, while a
reply is speaking. Three sizes:

- **Capsule**: project, one line of the summary, progress, and a badge for calls waiting on you
- **Panel** (chevron or badge): the full summary, a scrub bar, skip, and **your calls**: every unanswered
  decision from the calls window (Settings: 6 hours to 1 week) across all projects (arrows step through them).
  Order: pinned threads, then pinned projects, then projects you worked in lately (you typed in the session,
  or opened it in the Claude app, within Settings > "Put threads you worked in first", default 2 hours;
  a dot marks them), then the rest; newest first in each group. The star next to the project pins it
  (Shift+click pins only that thread); history rows and the right-click menu have the same toggle, and
  Settings > Behavior lists the pins with Remove.
  **Calls from Claude app Projects** (cloud threads) are pushed in, not polled: a session on this PC posts
  `POST /calls/push` with `{id, project, thread, question, options, url}` the moment a thread needs you
  (upserted by id, spoken, shown as "APP CALL"), and `POST /calls/push/<id>/done` closes it. A cloud thread
  can't be answered from here, so each option opens its `url` (claude.ai links only) or the Claude app. Pinned replies also jump ahead in the voice queue,
  without cutting off the one playing. Pick an
  option (or press 1-9), or type another option or a follow-up and press Enter: it is sent to that session
  with `claude --resume <id> -p` in the background, and the session's reply plays here. A call disappears
  once you answer it, dismiss it, or the session replies again. If you answer in the thread itself
  (you type a reply there after the question), the daemon sees it in the thread's transcript within a few
  seconds, marks the call "Answered in the thread", and the player drops it with a short notice.
  When one reply asks several questions they stay together as one call ("Question 1 of 3"): answer or skip
  (S) each one, check them on the review step (click a row to change it), then **Send answers** (Enter)
  delivers them to the session in one message. Nothing is sent until then, so the agent never acts on half
  the answers. The "Anything else?" box on the review step adds extra context or requests: they go last in
  the same message, after "Also:" (Enter makes a new line, Ctrl+Enter sends).
  Under each question, "About:" opens the context: a sentence or two on what the question refers to,
  any pictures the reply points at (click to open), links to previews, and the full reply, so there's no
  need to open the session first.
  Where the answer goes: a reply from a thread open in the **Claude desktop app** is answered in that thread.
  The player opens it, checks the header shows that thread's title, and types and sends the answer through
  Windows UI Automation. If the input box already holds a draft, or the thread can't be found, nothing is typed:
  the answer is copied and the call stays open. Other sessions (terminal, VS Code) are resumed in the background
  with `claude --resume <id> -p`. A background resume is invisible in an open desktop thread, which then goes
  out of date, so use "Background" only on purpose
- **Library** (Queue & history): up next and the last 7 days. Click a row for the full text, Replay,
  Open session, Answer and Copy resume. Background runs are counted, not listed

Click the project name to open the session it came from. Right-click for: hide for an hour, mute one noisy
project for an hour, minimize to an orb, clear the queue, quit. Esc or X hides it until the next voiceover.

**Minimize** (the dash button in the panel header, the dash that appears when you hover the capsule, or
right-click > "Minimize to an orb") shrinks the player
to a 40 px glossy ember orb that slides to the nearest side of the screen. It pulses while a reply speaks,
shows calls waiting as a small pill, and grows a little on hover (tooltip: "Claude VoicePlayer · 2 calls").
Click it and the player comes back exactly where it was; drag it and it settles on the nearest edge again.
The minimized state survives a restart. A new call
restores the player only when "Open the panel when a call arrives" is on.

**Bring it back**: the Start menu shortcut **Claude VoicePlayer** (`show_player.pyw`, icon in
`assets/ember-voice.ico`) restores a hidden or minimized player, or starts the daemon if it is down.
Scripts can do the same with `POST /show`. Keys (after
clicking the player): Space pause, Right skip, M mute, 1-9 pick an option.

### Settings

The gear button opens Settings. Changes apply at once and are saved to
`%LOCALAPPDATA%\local-tts\settings.json`:

| Setting | Choices | Default |
| --- | --- | --- |
| Theme (colours and type) | Ember (Outfit + DM Sans), Graphite (greys, silver buttons; Inter), Midnight (navy, blue; Space Grotesk headings + Inter), Daylight (warm cream; Fraunces headings + DM Sans), MadeFire (Night and Flame; Outfit + DM Sans, Flame pulse) | Ember |
| Panel layout | Classic (one column), Two lanes (playback on top, calls below: a new reply never moves a call) | Classic |
| Text size (scales the whole player) | S, M, L, XL, XXL | M |
| Player width (independent of text size) | Narrow, Default, Wide, Wider (0.85x to 1.4x) | Default |
| Opacity | 70, 80, 90, 100% | 100% |
| Pulse color (rim and glow) | Promethean Amber (MadeFire orange), Cooled Ember, Ember Light, Rose, Violet, Blue, Teal, White, Flame | Promethean Amber |
| Glow size (how far the glow reaches outside the rim) | Rim only, Small, Medium, Large, Largest | Medium |
| Pulse with the voice (rim and orb follow the voice's loudness; off: slow breath) | on/off | on |
| Reduce motion (panels change at once, fades stay; also on when Windows "Animation effects" is off) | on/off | off |
| Voice (click to hear it) | Heart, Bella, Nicole, Sarah, Michael, Adam, Emma (UK), George (UK) | Heart |
| Speaking speed | 0.9x to 1.4x | 1x |
| Say which project first | on/off | on |
| Summarize replies (off reads a cleaned-up excerpt) | on/off | on |
| Speak background runs | on/off | off |
| Open the panel when a call arrives | on/off | on |
| Hide when nothing is playing | on/off | off |
| Keep calls waiting for | 6h, 12h, 1 day, 3 days, 1 week | 3 days |
| Answers to Claude app threads | Type and send, Paste only, Background | Type and send |

"Restore defaults" and "Reset position" are at the bottom. Scripts can read and change the same values:
`GET /settings`, and `POST /settings` with a JSON object of the keys to change (unknown keys and values are
ignored). Changing the pulse color, glow size or pulse toggle plays a short preview pulse. To add a setting, add it to `SETTINGS_SCHEMA` in `voiced.py` and a control in
`Widget._settings_panel` in `player.py`.

Settings taller than the screen scroll (mouse wheel) under a fixed header, and the player never grows past
the screen's work area. Motion is short and eased out (about 150 to 250 ms, exits quicker than entries): the
panel settles out of the capsule, Settings comes in from the gear side, the next question slides in a few
pixels with its options staggered, and toasts rise. Nothing animates after a key press.

It is light: one canvas, no widget per row, and animations run only while something moves (about 1% of a
core idle, 5% while speaking).

Tests: `venv\Scripts\python.exe -m unittest test_voiced test_player_themes` (the second opens the real player
for every theme: panel, settings and its scroll, capsule hover, minimize and restore)

## License

MIT — see [LICENSE](LICENSE).

Model weights are distributed by [hexgrad](https://huggingface.co/hexgrad/Kokoro-82M) under Apache 2.0.

