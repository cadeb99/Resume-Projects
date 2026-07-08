# Vader — A Personal Voice-Driven AI Assistant

An always-on, voice-controlled AI assistant (Iron Man's JARVIS, basically) built in
Python: wake-word detection, real-time conversational voice control with tool use,
a scheduled morning briefing pipeline, and a long-term memory system — all running
locally on macOS with cloud LLM/TTS calls only where they add real value.

This isn't a tutorial project — it's been in daily personal use, and most of the
design decisions below came from hitting a real limitation, diagnosing it, and
fixing the actual root cause rather than a workaround.

## What it does

- **Wake-word voice control** — say the wake word, then talk naturally. Full
  conversation history is maintained across follow-up turns within a session.
- **Tool-calling agent** — the assistant can search the web, open apps, manage
  Google Calendar and Google Tasks (create/edit/delete, with a verbal confirmation
  step before anything destructive), check email and weather, and take/analyze a
  screenshot of the screen.
- **Morning briefing pipeline** — pulls calendar, tasks, email, and a 3-source
  weather consensus, has an LLM synthesize a natural spoken briefing, and speaks it
  with background music, scheduled via a time-window + "already ran today" gate
  rather than a fixed clock time (so it survives sleep/wake unreliability).
- **Long-term memory** — durable facts, corrections, ongoing project state, and
  known people/entities persist across sessions and get injected into context
  automatically, with async extraction so it never adds latency to a live turn.
- **Latency-tuned real-time voice loop** — every part of the wake-word → response
  pipeline has been profiled and optimized against the real running system, not
  guessed at (see below).

## Architecture

```
jarvis_listen.py     # always-on voice listener: wake word, conversation loop, tool dispatch
briefing.py          # scheduled entry point for the morning briefing
dashboard_server.py  # local web UI + orchestrates the real briefing pipeline
summarizer.py        # briefing script generation (Claude)
speak.py             # TTS + background music playback
scheduler.py         # time-window scheduling gate, daily song rotation
memory.py            # long-term memory: SQLite schema, read/write paths, consolidation
config.py            # all settings; secrets loaded from environment, never hardcoded
integrations/
    calendar_api.py  # Google Calendar (read + write)
    tasks_api.py     # Google Tasks (read + write)
    gmail_api.py     # Gmail, label-filtered
    weather_api.py   # NWS + Open-Meteo + OpenWeatherMap consensus
    google_auth.py   # shared OAuth
```

## Engineering decisions worth reading

**Memory: SQLite over a vector database.** This stores one person's durable facts —
realistically dozens to a few hundred rows even after years of daily use, never a
corpus. A vector index earns its cost when linear scan becomes the bottleneck, which
never happens at this scale; meanwhile semantic search requires an embedding call
*before* the query even starts, adding real latency to an already-tuned voice loop
for accuracy gains that don't matter at N=200. SQLite is also zero-dependency
(stdlib) and fully offline. If this ever became "fuzzy search over six months of raw
transcripts" instead of "recall known facts," that's a genuinely different,
corpus-scale problem — worth being able to say precisely when the tradeoff flips,
not just defaulting to the trendier tool.

**Memory read/write split.** Reads piggyback on the wake-word prefetch — the moment
the wake word fires, calendar/tasks/email/weather are already being fetched in
parallel on a background thread while you're still speaking; memory became a fifth
entry in that same pool. A capped SQLite read is sub-5ms — faster than any of the
network calls it runs alongside, so it's parallelized for consistency and headroom,
not because it's required for speed. Writes fire on a daemon thread at the exact
point a session's transcript is about to be discarded, calling a cheap model to
extract structured facts — this can take a second or two and nobody notices, because
it happens after the assistant has already stopped talking.

**Fact categories are more than "preference."** Corrections override conflicting
facts immediately rather than sitting alongside them. Temporal facts carry an
explicit expiry — a confidently-stated fact about a project that ended three months
ago is a trust-breaker, so anything with a shelf life is excluded from context once
it's stale rather than lingering. Inferred routines require repeated observation
before being promoted from a staged table into a real fact — a one-off mention
isn't a pattern. A "do not remember" instruction is enforced as a hard filter at
write time (exact match) *and* baked into the extraction prompt itself (semantic),
so a blocked topic can't sneak back in reworded.

**Real-time voice loop, profiled not guessed.** Every latency source was measured
against the live system before touching it: TTS model switched to ElevenLabs' Turbo
variant after benchmarking confirmed ~3x faster generation with no quality
regression; the wake-word audio stream was rearchitected from per-call device
reopens (~150-260ms overhead measured directly) to one persistent stream; redundant
fixed-delay sleeps were found and removed by tracing what they were actually
protecting against (nothing, by the time they ran). When Whisper's wake-word
transcription started returning a different wrong guess almost every attempt, the
fix wasn't another keyword — it was recognizing that behavior as a low-confidence
model symptom and upgrading the model tier, because the real signal (inconsistent
guesses, not one stable mishearing) pointed at model confidence, not vocabulary
coverage.

**Screenshot → paste into a live chat app, diagnosed against the real target.**
Automating a paste into an Electron app's compose box looked like a permissions
problem at first (Accessibility, Screen Recording) — but after methodically mapping
which coordinates succeeded vs. failed, the actual cause was that Electron's
web-rendered content isn't reliably reachable by macOS's accessibility-based UI
scripting at all. The fix was `cliclick`, which synthesizes real low-level input
events instead of going through the accessibility tree — verified end to end with
an isolated test before shipping it.

## Setup

```bash
pip install -r requirements.txt
brew install cliclick   # macOS UI automation for the screenshot → chat feature
```

Environment variables (never hardcoded — see `config.py`):

```
ANTHROPIC_API_KEY
ELEVENLABS_API_KEY
OPENWEATHERMAP_API_KEY
```

Google Calendar/Tasks/Gmail require OAuth credentials (`GOOGLE_CREDENTIALS_PATH` /
`GOOGLE_TOKEN_PATH` in `config.py`) from a Google Cloud project with those APIs
enabled.

Background music (`config.BACKGROUND_MUSIC_PLAYLIST`) isn't included — add your own
licensed/royalty-free audio files to `assets/` and list them there.

Run the voice listener:
```bash
python3 jarvis_listen.py
```

Run the briefing manually (bypassing the schedule gate):
```bash
python3 briefing.py --force
```

Run the memory system's test suite:
```bash
python3 test_memory.py
```

macOS also requires Screen Recording and Accessibility permissions granted to the
Python interpreter (System Settings → Privacy & Security) for the screenshot and
UI-automation features.
