"""
Vader voice listener — always-on conversational AI.

Uses Whisper for both wake word detection and command transcription,
since openWakeWord has compatibility issues with Python 3.14 on ARM Mac.

Flow:
  1. Listens in short 2-second chunks continuously
  2. Transcribes each chunk with Whisper (fast, local)
  3. If "vader" (or a close phonetic match) appears in the transcription — wake word detected
  4. Plays a soft chime, then records your follow-up command
  5. Transcribes the command and sends to Claude
  6. Speaks the response via ElevenLabs (same voice as briefing)

Sleep/wake:
  Say "Vader, sleep" / "Vader, go to sleep" / "Vader, mute"
    → Vader confirms and enters silent mode (still listens, ignores everything
      except the wake-up phrase)
  Say "Vader, wake up" / "Vader, wake"
    → Vader confirms and resumes full listening

Run with: python3 jarvis_listen.py
Stop with: Ctrl+C
"""

import sys
import os
import time
import tempfile
import wave
import struct
import re

import numpy as np
import sounddevice as sd
import whisper
import anthropic

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import speak
import memory

# --- Audio settings ---
SAMPLE_RATE = 16000
CHANNELS = 1
MIC_DEVICE_INDEX = 1         # MacBook Air Microphone (confirmed working)
WAKE_CHUNK_SECONDS = 2.5     # How long each "listening" chunk is. Raised back up from 1.5s —
                             # live logs showed wildly inconsistent mishearings of "Vader"
                             # (different every attempt, not one stable variant), pointing to
                             # insufficient audio context rather than a fixable spelling issue.
                             # Reliability matters more than the small latency win here.
COMMAND_SECONDS_MAX = 8.0    # Max command recording length
SILENCE_THRESHOLD = 300      # RMS below this = silence
SILENCE_SECONDS = 2.0        # Stop recording after this many seconds of silence (raised from 1.5)
CHUNK_SIZE = 1024            # For pyaudio recording

# --- Whisper settings ---
WHISPER_MODEL_SIZE = "small"  # "base" was giving a different wrong guess almost every
                               # attempt for the wake word — classic low-confidence behavior
                               # on short, context-free audio. "small" is ~2x slower per
                               # transcription (~0.4s vs ~0.2s, benchmarked) but meaningfully
                               # more accurate, and it's a real-time win for every command
                               # transcription too, not just the wake word.

# --- Wake word ---
# "vader" plus common Whisper mishearings of it. "better" added after
# confirming from live logs it was the dominant actual mishearing —
# "later"/"raider"/"trader" never once matched in practice.
WAKE_WORDS = ["vader", "later", "raider", "trader", "better"]

# --- Sleep/wake phrases ---
SLEEP_PHRASES = ["sleep", "go to sleep", "mute", "be quiet", "shut up", "take a break"]
WAKE_PHRASES = ["wake up", "wake"]


# --- Thinking filler phrases (pre-generated at startup in your ElevenLabs voice) ---
FILLER_PHRASES = [
    "Let me check on that.",
    "One moment, sir.",
    "Right.",
    "On it.",
    "Sure.",
    "Mm.",
]
FILLER_CACHE_DIR = os.path.join(os.path.expanduser("~/.jarvis"), "filler_cache")
_filler_files = []  # populated at startup


def generate_filler_cache():
    """
    Pre-generates 6 short filler phrases in your ElevenLabs voice at
    startup and saves them as local mp3 files. Playing them is then
    instant (local file, no network call) — used to fill the ~1.4s gap
    while Claude + ElevenLabs generate the real response.

    Falls back silently if ElevenLabs isn't configured or generation fails.
    """
    global _filler_files

    if not config.ELEVENLABS_API_KEY or not config.ELEVENLABS_VOICE_ID:
        return

    import requests
    os.makedirs(FILLER_CACHE_DIR, exist_ok=True)

    print("[Vader] Pre-generating filler phrases...")
    generated = []

    for i, phrase in enumerate(FILLER_PHRASES):
        cache_path = os.path.join(FILLER_CACHE_DIR, f"filler_{i}.mp3")

        # Skip if already cached from a previous run
        if os.path.exists(cache_path):
            generated.append(cache_path)
            continue

        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
            headers = {
                "xi-api-key": config.ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            }
            payload = {
                "text": phrase,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {
                    "stability": config.VOICE_STABILITY,
                    "similarity_boost": config.VOICE_SIMILARITY_BOOST,
                    "speed": config.VOICE_SPEED,
                },
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            with open(cache_path, "wb") as f:
                f.write(resp.content)
            generated.append(cache_path)
            print(f"[Vader]   Cached: '{phrase}'")
        except Exception as e:
            print(f"[Vader]   Failed to cache '{phrase}': {e}")

    _filler_files = generated
    print(f"[Vader] {len(generated)}/{len(FILLER_PHRASES)} filler phrases ready.")


def play_filler():
    """
    Plays a random pre-cached filler phrase instantly (local file,
    no network delay). Runs in a background thread so it doesn't
    block the Claude/ElevenLabs streaming that's already started.
    """
    if not _filler_files:
        return

    import random
    import subprocess
    import threading

    path = random.choice(_filler_files)
    threading.Thread(
        target=lambda: subprocess.run(["afplay", path]),
        daemon=True,
    ).start()


THANKS_PHRASES = [
    "My pleasure, sir.",
    "Thank you, sir.",
]
THANKS_CACHE_DIR = os.path.join(os.path.expanduser("~/.jarvis"), "thanks_cache")
_thanks_files = []  # populated at startup


def generate_thanks_cache():
    """
    Pre-generates the "thank you" acknowledgment phrases in your
    ElevenLabs voice at startup, same idea as the filler cache — so
    when you say "thanks", Vader responds instantly with zero Claude
    call and zero live TTS generation latency, instead of going through
    the normal filler + Claude + streaming pipeline.

    Falls back silently if ElevenLabs isn't configured or generation fails.
    """
    global _thanks_files

    if not config.ELEVENLABS_API_KEY or not config.ELEVENLABS_VOICE_ID:
        return

    import requests
    os.makedirs(THANKS_CACHE_DIR, exist_ok=True)

    print("[Vader] Pre-generating 'thank you' responses...")
    generated = []

    for i, phrase in enumerate(THANKS_PHRASES):
        cache_path = os.path.join(THANKS_CACHE_DIR, f"thanks_{i}.mp3")

        # Skip if already cached from a previous run
        if os.path.exists(cache_path):
            generated.append(cache_path)
            continue

        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
            headers = {
                "xi-api-key": config.ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            }
            payload = {
                "text": phrase,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {
                    "stability": config.VOICE_STABILITY,
                    "similarity_boost": config.VOICE_SIMILARITY_BOOST,
                    "speed": config.VOICE_SPEED,
                },
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            with open(cache_path, "wb") as f:
                f.write(resp.content)
            generated.append(cache_path)
            print(f"[Vader]   Cached: '{phrase}'")
        except Exception as e:
            print(f"[Vader]   Failed to cache '{phrase}': {e}")

    _thanks_files = generated
    print(f"[Vader] {len(generated)}/{len(THANKS_PHRASES)} 'thank you' responses ready.")


def is_thanks(text: str) -> bool:
    """Detects a simple thank-you so Vader can skip the filler/Claude
    round-trip entirely and respond instantly instead."""
    text_lower = text.lower().strip().strip(".,!")
    keywords = [
        "thank you", "thanks", "thank you so much", "thanks so much",
        "thank you very much", "thanks a lot", "appreciate it",
        "much appreciated", "thanks a bunch",
    ]
    return any(kw in text_lower for kw in keywords)


def play_thanks_response():
    """
    Speaks an instant "thank you" acknowledgment — plays a pre-cached
    phrase directly (blocking, since this IS the whole response, unlike
    play_filler() which just covers a gap while Claude keeps working
    on the real answer). Falls back to live TTS if the cache isn't ready.
    """
    import random

    if _thanks_files:
        import subprocess
        path = random.choice(_thanks_files)
        subprocess.run(["afplay", path])
    else:
        speak.speak(random.choice(THANKS_PHRASES))


# --- App discovery (populated at startup) ---
_installed_apps = {}  # lowercase name → exact app name e.g. {"spotify": "Spotify"}

# --- Pre-fetch cache (populated on each wake word detection) ---
_prefetch_cache = {}   # {"calendar": data, "tasks": data, "emails": data, "weather": data}
_prefetch_thread = None


def discover_apps():
    """
    Scans /Applications, ~/Applications, and the built-in macOS app
    folders at startup and builds a lookup table of every installed
    app. Enables fuzzy matching so "friendly streaming" finds "Friendly
    Streaming" automatically, regardless of exact capitalization or
    minor spelling differences.
    """
    global _installed_apps
    import glob

    app_dirs = [
        "/Applications",
        os.path.expanduser("~/Applications"),
        "/System/Applications",
        "/System/Applications/Utilities",
    ]
    found = {}

    for app_dir in app_dirs:
        for app_path in glob.glob(os.path.join(app_dir, "*.app")):
            app_name = os.path.basename(app_path).replace(".app", "")
            found[app_name.lower()] = app_name
            # Also index without common words to help matching
            # e.g. "friendly streaming" indexes as both full name and without spaces
            found[app_name.lower().replace(" ", "")] = app_name

    _installed_apps = found
    print(f"[Vader] Discovered {len(set(found.values()))} installed apps.")


def find_app(requested_name: str) -> str:
    """
    Fuzzy-matches a requested app name against installed apps.
    Returns the exact app name if found, or None if no match.

    Tries in order:
      1. Exact match (case-insensitive)
      2. Requested name is contained in an app name
      3. App name is contained in the requested name
      4. Word-by-word overlap scoring
    """
    req = requested_name.lower().strip()

    # 1. Exact match
    if req in _installed_apps:
        return _installed_apps[req]

    # 2. Request is a substring of an app name
    for key, name in _installed_apps.items():
        if req in key:
            return name

    # 3. App name is a substring of the request
    for key, name in _installed_apps.items():
        if key in req:
            return name

    # 4. Word overlap — score by how many words match
    req_words = set(req.split())
    best_score = 0
    best_match = None
    for key, name in _installed_apps.items():
        key_words = set(key.split())
        overlap = len(req_words & key_words)
        if overlap > best_score:
            best_score = overlap
            best_match = name

    if best_score > 0:
        return best_match

    return None


def load_whisper():
    print("[Vader] Loading speech recognition model...")
    model = whisper.load_model(WHISPER_MODEL_SIZE)
    print("[Vader] Model loaded.")
    return model


def play_chime():
    """Short confirmation tone so you know Vader heard you."""
    try:
        duration = 0.15
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
        tone = (np.sin(2 * np.pi * 880 * t) * 0.3).astype(np.float32)
        sd.play(tone, samplerate=SAMPLE_RATE, device=MIC_DEVICE_INDEX)
        sd.wait()
    except Exception:
        pass


def contains_wake_word(text: str) -> bool:
    """Returns True if any wake word appears in the transcribed text."""
    text_lower = text.lower().strip()
    return any(word in text_lower for word in WAKE_WORDS)


def is_sleep_command(text: str) -> bool:
    """Returns True if the command is asking Vader to go to sleep."""
    text_lower = text.lower().strip()
    return any(phrase in text_lower for phrase in SLEEP_PHRASES)


def is_wake_command(text: str) -> bool:
    """Returns True if the command is asking Vader to wake up."""
    text_lower = text.lower().strip()
    return any(phrase in text_lower for phrase in WAKE_PHRASES)


# --- Persistent mic stream ---
# Opened once at startup and reused by record_chunk/record_command/
# record_followup instead of each opening (and tearing down) its own —
# measured ~150-260ms of pure device-open overhead per call otherwise,
# paid on every single wake-word poll plus every recording start.
_pa = None
_mic_stream = None


def open_mic_stream():
    """Opens the one persistent input stream for the program's lifetime."""
    global _pa, _mic_stream
    import pyaudio

    _pa = pyaudio.PyAudio()
    _mic_stream = _pa.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK_SIZE,
        input_device_index=MIC_DEVICE_INDEX,
    )


def close_mic_stream():
    """Releases the persistent mic stream on shutdown."""
    global _pa, _mic_stream
    if _mic_stream is not None:
        _mic_stream.stop_stream()
        _mic_stream.close()
    if _pa is not None:
        _pa.terminate()
    _mic_stream = None
    _pa = None


def _flush_mic_buffer():
    """Discards whatever audio piled up in the mic buffer while nothing
    was reading from it (e.g. while Vader was speaking a response), so
    the next read starts from live audio instead of a stale backlog."""
    if _mic_stream is None:
        return
    available = _mic_stream.get_read_available()
    if available > 0:
        _mic_stream.read(available, exception_on_overflow=False)


def record_chunk(seconds: float) -> np.ndarray:
    """Records a fixed-length audio chunk from the persistent mic stream
    and returns it as a float32 array."""
    _flush_mic_buffer()
    n_reads = max(1, int(seconds * SAMPLE_RATE / CHUNK_SIZE))
    frames = [_mic_stream.read(CHUNK_SIZE, exception_on_overflow=False) for _ in range(n_reads)]
    raw = b"".join(frames)
    audio_int16 = np.frombuffer(raw, dtype=np.int16)
    return audio_int16.astype(np.float32) / 32768.0


def record_command(initial_wait_seconds: float = 1.0) -> tuple:
    """
    Records audio until silence is detected or max duration is hit.
    Returns (audio_float32, spoke_immediately) where spoke_immediately
    is True if speech was detected within the first second — used to
    decide whether Vader should acknowledge before waiting for a command.

    initial_wait_seconds: how long to wait for speech to start before
    giving up — default 1s for immediate commands, use 2.5s after an
    acknowledgment so you have time to gather your thoughts.
    """
    _flush_mic_buffer()

    frames = []
    silent_chunks = 0
    max_silent = int(SILENCE_SECONDS * SAMPLE_RATE / CHUNK_SIZE)
    max_total = int(COMMAND_SECONDS_MAX * SAMPLE_RATE / CHUNK_SIZE)
    max_initial_wait = int(initial_wait_seconds * SAMPLE_RATE / CHUNK_SIZE)
    chunks_per_second = int(SAMPLE_RATE / CHUNK_SIZE)
    total = 0
    started = False
    spoke_immediately = False

    while total < max_total:
        data = _mic_stream.read(CHUNK_SIZE, exception_on_overflow=False)
        frames.append(data)
        total += 1

        samples = struct.unpack(f"{CHUNK_SIZE}h", data)
        rms = (sum(s * s for s in samples) / CHUNK_SIZE) ** 0.5

        if rms > SILENCE_THRESHOLD:
            if not started and total <= chunks_per_second:
                spoke_immediately = True
            started = True
            silent_chunks = 0
        elif started:
            silent_chunks += 1
            if silent_chunks >= max_silent:
                break
        elif not started and total >= max_initial_wait:
            # Nobody started speaking within the initial wait window — stop
            break

    raw = b"".join(frames)
    audio_int16 = np.frombuffer(raw, dtype=np.int16)
    return audio_int16.astype(np.float32) / 32768.0, spoke_immediately


def record_followup(wait_seconds: float = 3.0):
    """
    Listens for a follow-up question after Vader responds. Waits up to
    wait_seconds for speech to start. Returns (audio, detected) where
    detected is False if no speech started within the window (meaning
    the conversation is over and we should drop back to wake word mode).
    """
    _flush_mic_buffer()

    frames = []
    max_wait_chunks = int(wait_seconds * SAMPLE_RATE / CHUNK_SIZE)
    max_silent = int(SILENCE_SECONDS * SAMPLE_RATE / CHUNK_SIZE)
    max_total = int(COMMAND_SECONDS_MAX * SAMPLE_RATE / CHUNK_SIZE)
    total = 0
    started = False
    silent_chunks = 0

    while total < max_total:
        data = _mic_stream.read(CHUNK_SIZE, exception_on_overflow=False)
        frames.append(data)
        total += 1

        samples = struct.unpack(f"{CHUNK_SIZE}h", data)
        rms = (sum(s * s for s in samples) / CHUNK_SIZE) ** 0.5

        if rms > SILENCE_THRESHOLD:
            started = True
            silent_chunks = 0
        elif started:
            silent_chunks += 1
            if silent_chunks >= max_silent:
                break
        elif not started and total >= max_wait_chunks:
            # No speech detected within the wait window — conversation over
            return None, False

    raw = b"".join(frames)
    audio_int16 = np.frombuffer(raw, dtype=np.int16)
    return audio_int16.astype(np.float32) / 32768.0, True


def transcribe(audio: np.ndarray, whisper_model) -> str:
    """Transcribes a float32 audio array using Whisper."""
    result = whisper_model.transcribe(audio, language="en", fp16=False)
    return result["text"].strip()


def ask_claude(user_text: str, history: list = None) -> str:
    """
    Sends the command to Claude and returns a spoken response.
    Accepts conversation history for multi-turn context so follow-up
    questions like 'what about tomorrow?' make sense.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    system_prompt = _jarvis_system_prompt()
    messages = list(history) if history else []
    messages.append({"role": "user", "content": user_text})

    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=300,
        system=system_prompt,
        messages=messages,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
    )

    text_parts = [block.text for block in response.content if hasattr(block, "text")]
    return " ".join(text_parts).strip()


def get_calendar_events(days_ahead: int = 1) -> str:
    """Fetches events from Google Calendar for the next N days. Each
    line includes the event's ID so Claude can reference a specific
    event later for editing or deleting it."""
    try:
        from datetime import datetime
        from integrations import calendar_api

        events = calendar_api.get_upcoming_events(days_ahead=days_ahead)
        if not events:
            return "No upcoming events found in Google Calendar."

        lines = []
        for e in events:
            try:
                dt = datetime.fromisoformat(e["start"].replace("Z", "+00:00")).astimezone()
                time_str = dt.strftime("%A %B %d at %I:%M %p").lstrip("0")
            except Exception:
                time_str = e["start"]
            lines.append(f"{e['title']} — {time_str} [event_id: {e['id']}]")

        return "\n".join(lines)
    except Exception as e:
        return f"Could not access Google Calendar: {e}"


def get_tasks() -> str:
    """Fetches open tasks from Google Tasks. Each line includes the
    task's ID so Claude can reference a specific task later for
    editing, completing, or deleting it."""
    try:
        from integrations import tasks_api

        tasks = tasks_api.get_open_tasks()
        if not tasks:
            return "No open tasks found in Google Tasks."

        lines = []
        for t in tasks:
            due = t.get("due", "No due date")
            lines.append(f"{t['title']} ({due}) [task_id: {t['id']}]")

        return "\n".join(lines)
    except Exception as e:
        return f"Could not access Google Tasks: {e}"


def get_emails() -> str:
    """Fetches unread emails from your important Gmail label."""
    try:
        from googleapiclient.discovery import build
        from integrations.google_auth import get_credentials

        creds = get_credentials()
        service = build("gmail", "v1", credentials=creds)

        query = f"label:{config.GMAIL_IMPORTANT_LABEL} is:unread"
        results = service.users().messages().list(userId="me", q=query).execute()
        messages = results.get("messages", [])

        if not messages:
            return f"No unread emails in your {config.GMAIL_IMPORTANT_LABEL} label."

        lines = []
        for ref in messages[:5]:
            msg = service.users().messages().get(
                userId="me", id=ref["id"], format="metadata",
                metadataHeaders=["From", "Subject"],
            ).execute()
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            sender = headers.get("From", "Unknown")
            if "<" in sender:
                sender = sender.split("<")[0].strip().strip('"')
            subject = headers.get("Subject", "No subject")
            lines.append(f"From {sender}: {subject}")

        return "\n".join(lines)
    except Exception as e:
        return f"Could not access Gmail: {e}"


def get_current_weather() -> str:
    """Fetches current weather using the same integration as the morning briefing."""
    try:
        from integrations.weather_api import get_todays_weather
        w = get_todays_weather()
        return (
            f"Conditions: {w.get('condition', 'unknown')}. "
            f"High: {w.get('high', '?')}°F, Low: {w.get('low', '?')}°F. "
            f"Wind: {w.get('wind_speed_mph', '?')} mph from the {w.get('wind_direction', '?')}"
            + (f", gusting to {w['wind_gust_mph']} mph" if w.get('wind_gust_mph') else "")
            + f". Precip chance: {w.get('precip_chance', '?')}%."
        )
    except Exception as e:
        return f"Could not fetch weather: {e}"


SCREENSHOT_DIR = os.path.join(os.path.expanduser("~/.jarvis"), "screenshots")
CLICLICK_PATH = "/opt/homebrew/bin/cliclick"  # brew install cliclick


def take_screenshot_and_analyze(question: str) -> str:
    """
    Captures the screen, asks Claude (vision) about it, and stages the
    same image as an attachment in the user's open Claude desktop app —
    pasted into the compose box, never auto-sent, since sending on the
    user's behalf into a real conversation without them choosing to isn't
    something to do automatically. Returns the spoken analysis.

    Requires:
      - `cliclick` (brew install cliclick) — Claude Desktop is Electron-
        based, and its actual chat/compose area is rendered web content
        that macOS's accessibility-based automation (System Events
        click-at/keystroke) cannot reliably reach — confirmed by testing
        directly against the app. cliclick synthesizes real, low-level
        mouse/keyboard events instead, which works regardless of how the
        target UI is rendered.
      - Screen Recording permission granted to the Python interpreter
        running this (System Settings > Privacy & Security) — for the
        screenshot itself.
      - Accessibility permission for the same interpreter — required by
        cliclick to post synthetic input events at all.
    All failure points degrade gracefully with a spoken explanation
    rather than raising.
    """
    import subprocess
    import base64
    from datetime import datetime

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOT_DIR, f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

    result = subprocess.run(["screencapture", "-x", path], capture_output=True)
    if result.returncode != 0 or not os.path.exists(path):
        return "I couldn't take a screenshot, sir — Screen Recording permission may not be granted to Python."

    try:
        with open(path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=90,
            system=(
                "You're describing a screenshot out loud to someone, as a spoken voice response. "
                "Answer in exactly 1-2 short, plain conversational sentences — be brief, no matter "
                "how much is on screen. Never use markdown, headers, bullet points, or asterisks — "
                "this will be spoken aloud by a TTS engine that reads symbols literally. Focus only "
                "on what's most relevant to the question asked; skip everything else."
            ),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                    {"type": "text", "text": question},
                ],
            }],
        )
        analysis = "".join(b.text for b in response.content if hasattr(b, "text")).strip()
    except Exception as e:
        analysis = f"I took the screenshot but couldn't analyze it, sir — {e}"

    try:
        subprocess.run(
            ["osascript", "-e", f'set the clipboard to (read (POSIX file "{path}") as «class PNGf»)'],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["osascript", "-e", 'tell application "Claude" to activate'],
            check=True, capture_output=True,
        )
        time.sleep(1.0)

        # Activating a window brings it to front but doesn't guarantee
        # keyboard focus lands in the message box, so a screenshot + click
        # is taken to find and focus it before pasting. Uses a fresh
        # screenshot of the now-frontmost Claude window, not the original
        # one (which may have captured a different app).
        locator_path = path.replace(".png", "_locator.png")
        subprocess.run(["screencapture", "-x", locator_path], capture_output=True)
        clicked = _click_into_compose_box(locator_path)
        if os.path.exists(locator_path):
            os.remove(locator_path)

        if clicked:
            time.sleep(0.3)
            # Claude Desktop is Electron-based — its chat/compose area is
            # rendered web content that macOS's accessibility-based
            # `System Events keystroke` silently fails to reach (confirmed
            # by testing: it works fine on native UI chrome, not here).
            # cliclick synthesizes a real, low-level key event instead —
            # the same fix already used for the click above.
            subprocess.run(
                [CLICLICK_PATH, "kd:cmd", "t:v", "ku:cmd"],
                check=True, capture_output=True,
            )
        else:
            analysis += " I couldn't find the message box to paste it into though, sir."
    except Exception as e:
        print(f"[Vader] Couldn't stage screenshot in Claude app: {e}")
        analysis += " I couldn't get it into your Claude chat though, sir."

    return analysis


def _get_logical_screen_size() -> tuple:
    """Returns (width, height) in logical points — what System Events'
    click-at coordinates expect, NOT raw screenshot pixels (screenshots
    are captured at 2x on Retina displays)."""
    import subprocess

    result = subprocess.run(
        ["osascript", "-e", 'tell application "Finder" to get bounds of window of desktop'],
        capture_output=True, text=True,
    )
    parts = [int(p.strip()) for p in result.stdout.strip().split(",")]
    return parts[2], parts[3]


def _click_into_compose_box(screenshot_path: str) -> bool:
    """
    Asks Claude (vision) where the message/chat input box is in the given
    screenshot, as a FRACTION of image width/height (sidesteps needing to
    know the exact Retina scale factor), then clicks there so a following
    paste lands in the right place. Returns True if it found and clicked
    a plausible location.
    """
    import subprocess
    import base64

    with open(screenshot_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=50,
            system=(
                "You locate UI elements in screenshots. Respond with ONLY two numbers separated "
                "by a comma: the x and y location of the main text message/chat input box (where "
                "someone would click to type a new message), as a fraction of image width and "
                "height (0.0 to 1.0 each). Example: 0.5,0.92 . If there is no visible message "
                "input box, respond exactly: none"
            ),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                    {"type": "text", "text": "Where is the message input box?"},
                ],
            }],
        )
        text = "".join(b.text for b in response.content if hasattr(b, "text")).strip()
        if text.lower() == "none" or "," not in text:
            return False
        x_frac, y_frac = (float(p.strip()) for p in text.split(","))
    except Exception as e:
        print(f"[Vader] Couldn't locate compose box: {e}")
        return False

    screen_w, screen_h = _get_logical_screen_size()
    click_x, click_y = round(x_frac * screen_w), round(y_frac * screen_h)

    if not os.path.exists(CLICLICK_PATH):
        print(f"[Vader] cliclick not found at {CLICLICK_PATH} — install with `brew install cliclick`.")
        return False

    # System Events' accessibility-based `click at` silently fails on
    # Electron apps' web-rendered content (confirmed by testing against
    # the real Claude app — it worked on native sidebar chrome but not the
    # chat/compose area). cliclick synthesizes a real, low-level mouse
    # click instead, which works regardless of how the target is rendered.
    result = subprocess.run([CLICLICK_PATH, f"c:{click_x},{click_y}"], capture_output=True)
    return result.returncode == 0


def stream_claude_sentences(user_text: str, history: list = None):
    """
    Streams Claude's response and yields complete sentences as they
    arrive. Supports web search — if Claude decides to search the web,
    falls back to a non-streaming tool-use loop (since web search
    latency dominates anyway) then yields the final response as sentences.
    """
    import re
    import subprocess as sp
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    messages = list(history) if history else []
    messages.append({"role": "user", "content": user_text})

    tools = [
        {"type": "web_search_20250305", "name": "web_search"},
        {
            "name": "open_browser",
            "description": (
                "Opens a URL in the user's default web browser on their screen. "
                "Use this when the user asks to 'pull up', 'open', 'show me', or 'find' "
                "a web page, recipe, article, video, or any specific content they want "
                "to view. After searching for the best URL, call this tool to open it. "
                "Always also give a brief spoken summary of what you're opening."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL to open in the browser.",
                    },
                    "description": {
                        "type": "string",
                        "description": "A 1-2 sentence spoken summary of what's being opened and why it's relevant — this is the ONLY thing spoken to the user, so make it complete and useful. Example: 'I found a Gordon Ramsay beef wellington recipe on BBC Good Food — it looks like a solid one, pulling it up now.'",
                    },
                },
                "required": ["url", "description"],
            },
        },
        {
            "name": "open_app",
            "description": (
                "Opens a macOS application by name. Use this when the user asks to "
                "open, launch, or start an app — for example 'open Spotify', "
                "'launch Safari', 'start Xcode', 'open my email'. Pass the app name "
                "exactly as it appears in the Applications folder. Common examples: "
                "Spotify, Safari, Google Chrome, Mail, Messages, Calendar, Notes, "
                "Finder, Terminal, Slack, Zoom, Discord, VS Code, Photos, Music, "
                "FaceTime, Maps, Reminders."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "The exact name of the app to open, as it appears in the Applications folder. E.g. 'Spotify', 'Google Chrome', 'VS Code'.",
                    },
                },
                "required": ["app_name"],
            },
        },
        {
            "name": "take_screenshot",
            "description": (
                "Captures a screenshot of the user's current screen, analyzes it with vision "
                "to answer a question about what's on screen (or gives a general description "
                "if the user didn't ask something specific), and stages it as an attachment in "
                "the user's open Claude desktop app (pasted into the compose box — NOT sent; "
                "the user still hits send themselves). Use this whenever the user asks Vader to "
                "look at, check, describe their screen, or to send/upload a screenshot to Claude."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "What the user wants to know about their screen, verbatim or paraphrased. If they just said 'take a screenshot' with no specific question, use 'Describe what's on my screen.'",
                    },
                },
                "required": ["question"],
            },
        },
        {
            "name": "get_calendar",
            "description": (
                "Fetches upcoming events from the user's Google Calendar. "
                "Use this when the user asks about their schedule, calendar, "
                "upcoming events, what they have today/tomorrow/this week, "
                "or anything related to their appointments or meetings. "
                "Always use Google Calendar specifically, not Apple Calendar."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "How many days of events to fetch. 1 = today only, 7 = this week, etc. Default 1.",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "get_tasks",
            "description": (
                "Fetches open/incomplete tasks from the user's Google Tasks. "
                "Use this when the user asks about their to-do list, tasks, "
                "what they need to do, or their priorities."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "get_emails",
            "description": (
                "Fetches unread emails from the user's important Gmail label. "
                "Use this when the user asks about their email, messages, "
                "or what's in their inbox."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "get_weather",
            "description": (
                "Fetches the current weather forecast for the user's location. "
                "Use this when the user asks about weather, temperature, wind, "
                "or conditions outside."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "add_calendar_event",
            "description": (
                "Creates a new event on the user's Google Calendar. Use this when "
                "the user asks to add, create, schedule, or book something on their "
                "calendar. Supports both normal timed events and all-day events — "
                "only use all_day=true if the user specifically asks for an all-day "
                "event; otherwise default to a timed event."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The event title/summary."},
                    "start_datetime": {
                        "type": "string",
                        "description": "Event start. For a normal timed event: an ISO 8601 datetime WITH the same UTC offset shown in 'Current date and time' above, e.g. '2026-07-02T15:00:00-06:00'. For an all_day=true event: just the date, e.g. '2026-07-04'. Compute this from what the user said (e.g. 'tomorrow at 3pm', or 'the 4th of July').",
                    },
                    "end_datetime": {
                        "type": "string",
                        "description": "Event end. For a timed event: same ISO 8601 datetime format with offset — default to 30-60 minutes after start if no duration was given. For an all_day=true event: the LAST date the event covers, inclusive (e.g. a single-day event uses the same date as start_datetime; a 3-day event uses start + 2 days) — do not add an extra day yourself, that's handled automatically.",
                    },
                    "description": {"type": "string", "description": "Optional event notes/description."},
                    "all_day": {"type": "boolean", "description": "True only if the user specifically wants an all-day event. Defaults to false (a normal timed event)."},
                },
                "required": ["title", "start_datetime", "end_datetime"],
            },
        },
        {
            "name": "edit_calendar_event",
            "description": (
                "Edits an existing Google Calendar event's title, time, or "
                "description. You MUST already know the event_id from a prior "
                "get_calendar call or the pre-fetched calendar data — never guess "
                "an ID; call get_calendar first if you don't have it. IMPORTANT: "
                "before calling this tool, first respond with a spoken question "
                "confirming exactly what you're about to change, and do NOT call "
                "this tool yet. Only call it on the user's next turn if they "
                "clearly confirm (e.g. 'yes', 'do it', 'confirm')."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "The Google Calendar event ID to edit, from the [event_id: ...] tag."},
                    "title": {"type": "string", "description": "New title, if changing it."},
                    "start_datetime": {"type": "string", "description": "New start time, ISO 8601 with UTC offset (or a plain date if all_day=true), if changing it."},
                    "end_datetime": {"type": "string", "description": "New end time, ISO 8601 with UTC offset (or the last inclusive date if all_day=true), if changing it."},
                    "description": {"type": "string", "description": "New description, if changing it."},
                    "all_day": {"type": "boolean", "description": "Set true if start_datetime/end_datetime above are plain dates for converting to/keeping an all-day event. Defaults to false."},
                },
                "required": ["event_id"],
            },
        },
        {
            "name": "delete_calendar_event",
            "description": (
                "Permanently deletes an event from the user's Google Calendar. You "
                "MUST already know the event_id from a prior get_calendar call or "
                "the pre-fetched calendar data — never guess an ID; call "
                "get_calendar first if you don't have it. IMPORTANT: before calling "
                "this tool, first respond with a spoken question confirming exactly "
                "which event you're about to delete, and do NOT call this tool yet. "
                "Only call it on the user's next turn if they clearly confirm "
                "(e.g. 'yes', 'do it', 'confirm')."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "The Google Calendar event ID to delete, from the [event_id: ...] tag."},
                },
                "required": ["event_id"],
            },
        },
        {
            "name": "add_task",
            "description": (
                "Adds a new task to the user's Google Tasks list. Use this when the "
                "user asks to add a to-do, task, or reminder item (not a calendar "
                "event with a specific time)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The task title."},
                    "due": {"type": "string", "description": "Optional due date as an ISO 8601 date, e.g. '2026-07-05'. Omit if no due date was mentioned."},
                    "notes": {"type": "string", "description": "Optional task notes."},
                },
                "required": ["title"],
            },
        },
        {
            "name": "edit_task",
            "description": (
                "Edits an existing Google Tasks item's title, due date, or notes. "
                "You MUST already know the task_id from a prior get_tasks call or "
                "the pre-fetched tasks data — never guess an ID; call get_tasks "
                "first if you don't have it. IMPORTANT: before calling this tool, "
                "first respond with a spoken question confirming exactly what "
                "you're about to change, and do NOT call this tool yet. Only call "
                "it on the user's next turn if they clearly confirm."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The Google Tasks ID to edit, from the [task_id: ...] tag."},
                    "title": {"type": "string", "description": "New title, if changing it."},
                    "due": {"type": "string", "description": "New due date (ISO 8601 date), if changing it."},
                    "notes": {"type": "string", "description": "New notes, if changing them."},
                },
                "required": ["task_id"],
            },
        },
        {
            "name": "complete_task",
            "description": (
                "Marks a Google Tasks item as completed/done. Use this when the "
                "user says they finished, completed, or want to check off a task. "
                "You MUST already know the task_id from a prior get_tasks call or "
                "the pre-fetched tasks data — never guess an ID; call get_tasks "
                "first if you don't have it."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The Google Tasks ID to mark complete, from the [task_id: ...] tag."},
                },
                "required": ["task_id"],
            },
        },
        {
            "name": "delete_task",
            "description": (
                "Permanently deletes a task from the user's Google Tasks list. You "
                "MUST already know the task_id from a prior get_tasks call or the "
                "pre-fetched tasks data — never guess an ID; call get_tasks first "
                "if you don't have it. IMPORTANT: before calling this tool, first "
                "respond with a spoken question confirming exactly which task "
                "you're about to delete, and do NOT call this tool yet. Only call "
                "it on the user's next turn if they clearly confirm."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "The Google Tasks ID to delete, from the [task_id: ...] tag."},
                },
                "required": ["task_id"],
            },
        },
    ]

    buffer = ""
    sentence_end = re.compile(r'(?<=[.!?])\s+')
    full_response = []

    def yield_sentences(text):
        """Helper to split text into sentences and yield each."""
        nonlocal buffer
        buffer += text
        parts = sentence_end.split(buffer)
        if len(parts) > 1:
            for sentence in parts[:-1]:
                if sentence.strip():
                    full_response.append(sentence.strip())
                    yield sentence.strip()
            buffer = parts[-1]

    try:
        with client.messages.stream(
            model=config.CLAUDE_MODEL,
            max_tokens=150,
            system=_jarvis_system_prompt(),
            messages=messages,
            tools=tools,
        ) as stream:
            # Collect sentences without yielding yet — need to know if
            # Claude will use a tool before we start speaking
            pending_sentences = []
            for chunk in stream.text_stream:
                buffer += chunk
                parts = sentence_end.split(buffer)
                if len(parts) > 1:
                    for sentence in parts[:-1]:
                        if sentence.strip():
                            pending_sentences.append(sentence.strip())
                    buffer = parts[-1]

            final = stream.get_final_message()

        # Check if Claude wanted to use a tool
        if final.stop_reason == "tool_use":
            # Tool use — discard any pre-tool text, tool handler speaks instead
            messages.append({"role": "assistant", "content": final.content})

            # Process tool calls
            tool_results = []
            opened_url = None

            for block in final.content:
                if block.type == "tool_use":
                    if block.name == "open_browser":
                        # Execute browser open immediately
                        url = block.input.get("url", "")
                        desc = block.input.get("description", "I've pulled that up for you, sir.")
                        if url:
                            sp.Popen(["open", url])
                            opened_url = url
                            print(f"[Vader] Opened: {url}")
                        # Speak the summary Claude provided — this is the only response
                        if desc:
                            full_response.append(desc)
                            yield desc
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Opened {url} in the browser successfully.",
                        })

                    elif block.name == "open_app":
                        app_name = block.input.get("app_name", "")
                        if app_name:
                            # Try fuzzy match against discovered apps first
                            matched_name = find_app(app_name)
                            launch_name = matched_name or app_name
                            result = sp.run(["open", "-a", launch_name], capture_output=True)
                            if result.returncode == 0:
                                confirmation = f"Opening {launch_name}, sir."
                                print(f"[Vader] Launched: {launch_name}")
                            else:
                                confirmation = f"I couldn't find {app_name} on your system, sir."
                                print(f"[Vader] App not found: {app_name}")
                            full_response.append(confirmation)
                            yield confirmation
                            opened_url = app_name  # reuse flag to skip second response
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Launched {launch_name}." if result.returncode == 0 else f"Could not find {app_name}.",
                        })

                    elif block.name == "take_screenshot":
                        question = block.input.get("question", "Describe what's on my screen.")
                        confirmation = take_screenshot_and_analyze(question)
                        full_response.append(confirmation)
                        yield confirmation
                        opened_url = "handled"  # reuse flag to skip second Claude round-trip
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": confirmation,
                        })

                    elif block.name in (
                        "add_calendar_event", "edit_calendar_event", "delete_calendar_event",
                        "add_task", "edit_task", "complete_task", "delete_task",
                    ):
                        # Action tools that mutate Google Calendar/Tasks — execute
                        # immediately and speak a confirmation (Claude is instructed
                        # to have already gotten a verbal yes before calling the
                        # edit/delete variants).
                        from integrations import calendar_api, tasks_api

                        try:
                            if block.name == "add_calendar_event":
                                calendar_api.create_event(
                                    block.input.get("title", "Untitled event"),
                                    block.input.get("start_datetime"),
                                    block.input.get("end_datetime"),
                                    description=block.input.get("description", ""),
                                    all_day=block.input.get("all_day", False),
                                )
                                confirmation = f"Added \"{block.input.get('title', 'that event')}\" to your calendar, sir."
                            elif block.name == "edit_calendar_event":
                                calendar_api.update_event(
                                    block.input.get("event_id", ""),
                                    title=block.input.get("title"),
                                    start_datetime=block.input.get("start_datetime"),
                                    end_datetime=block.input.get("end_datetime"),
                                    description=block.input.get("description"),
                                    all_day=block.input.get("all_day", False),
                                )
                                confirmation = "Updated that event, sir."
                            elif block.name == "delete_calendar_event":
                                calendar_api.delete_event(block.input.get("event_id", ""))
                                confirmation = "Done — that event's been removed, sir."
                            elif block.name == "add_task":
                                tasks_api.create_task(
                                    block.input.get("title", "Untitled task"),
                                    due=block.input.get("due"),
                                    notes=block.input.get("notes", ""),
                                )
                                confirmation = f"Added \"{block.input.get('title', 'that task')}\" to your tasks, sir."
                            elif block.name == "edit_task":
                                tasks_api.update_task(
                                    block.input.get("task_id", ""),
                                    title=block.input.get("title"),
                                    due=block.input.get("due"),
                                    notes=block.input.get("notes"),
                                )
                                confirmation = "Updated that task, sir."
                            elif block.name == "complete_task":
                                tasks_api.complete_task(block.input.get("task_id", ""))
                                confirmation = "Marked that one complete, sir."
                            elif block.name == "delete_task":
                                tasks_api.delete_task(block.input.get("task_id", ""))
                                confirmation = "Done — that task's been removed, sir."
                        except Exception as ex:
                            print(f"[Vader] {block.name} failed: {ex}")
                            confirmation = f"Something went wrong on my end, sir — I couldn't do that."

                        full_response.append(confirmation)
                        yield confirmation
                        opened_url = "handled"  # reuse flag to skip second Claude round-trip
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": confirmation,
                        })
                    else:
                        # Data tools — use pre-fetched cache if available,
                        # otherwise fetch fresh (cache may not be ready yet
                        # if command came in very quickly after wake word)
                        if _prefetch_thread: _prefetch_thread.join(timeout=0.5)  # wait briefly if still fetching

                        if block.name == "get_calendar":
                            result_content = _prefetch_cache.get(
                                "calendar",
                                get_calendar_events(days_ahead=block.input.get("days_ahead", 7))
                            )
                        elif block.name == "get_tasks":
                            result_content = _prefetch_cache.get("tasks", get_tasks())
                        elif block.name == "get_emails":
                            result_content = _prefetch_cache.get("emails", get_emails())
                        elif block.name == "get_weather":
                            result_content = _prefetch_cache.get("weather", get_current_weather())
                        else:
                            result_content = "Tool executed."

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_content,
                        })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # If we already opened a browser and spoke a confirmation,
            # don't make another Claude call — that's the double-response bug.
            if opened_url:
                pass
            else:
                # Get Claude's final response after non-browser tool use (e.g. web search)
                tool_response = client.messages.create(
                    model=config.CLAUDE_MODEL,
                    max_tokens=150,
                    system=_jarvis_system_prompt(),
                    messages=messages,
                    tools=tools,
                )
                text_parts = [b.text for b in tool_response.content if hasattr(b, "text")]
                final_text = " ".join(text_parts).strip()
                if final_text:
                    for sentence in sentence_end.split(final_text):
                        if sentence.strip():
                            full_response.append(sentence.strip())
                            yield sentence.strip()

        else:
            # No tool use — yield the sentences we collected during streaming
            for sentence in pending_sentences:
                full_response.append(sentence)
                yield sentence

    except Exception as e:
        # If streaming fails entirely, fall back to non-streaming
        print(f"[Vader] Stream error, falling back: {e}")
        response = ask_claude(user_text, history)
        for sentence in sentence_end.split(response):
            if sentence.strip():
                full_response.append(sentence.strip())
                yield sentence.strip()

    # Flush any remaining buffer
    if buffer.strip():
        full_response.append(buffer.strip())
        yield buffer.strip()

    stream_claude_sentences.last_full_response = " ".join(full_response)


def speak_streaming_response(user_text: str, history: list = None) -> str:
    """
    Streams Claude's response sentence by sentence, generating ElevenLabs
    audio for each sentence as it arrives and playing it while the next
    is being generated. Returns the full response text for history tracking.

    Falls back to the non-streaming path if ElevenLabs isn't configured.
    """
    if not config.ELEVENLABS_API_KEY:
        response = ask_claude(user_text, history)
        speak.speak(response)
        return response

    import requests
    import queue
    import threading
    import tempfile
    import subprocess

    audio_queue = queue.Queue()
    SENTINEL = object()
    sentence_generator = stream_claude_sentences(user_text, history)

    def producer():
        try:
            for sentence in sentence_generator:
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
                headers = {
                    "xi-api-key": config.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                }
                payload = {
                    "text": sentence,
                    "model_id": "eleven_turbo_v2_5",  # low-latency model, ~3x faster than multilingual_v2
                    "voice_settings": {
                        "stability": config.VOICE_STABILITY,
                        "similarity_boost": config.VOICE_SIMILARITY_BOOST,
                        "speed": config.VOICE_SPEED,
                    },
                }
                try:
                    resp = requests.post(url, json=payload, headers=headers, timeout=30)
                    resp.raise_for_status()
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                        f.write(resp.content)
                        audio_queue.put(f.name)
                except Exception as e:
                    print(f"[Vader] ElevenLabs error: {e}")
        finally:
            audio_queue.put(SENTINEL)

    threading.Thread(target=producer, daemon=True).start()

    while True:
        item = audio_queue.get()
        if item is SENTINEL:
            break
        subprocess.run(["afplay", item])
        os.remove(item)

    return getattr(stream_claude_sentences, "last_full_response", "")


def _jarvis_system_prompt() -> str:
    from datetime import datetime

    installed = sorted(set(_installed_apps.values()))
    app_list = ", ".join(installed[:80]) if installed else "unknown"
    now_str = datetime.now().astimezone().strftime("%A, %B %d, %Y, %I:%M %p (%z)").replace("  ", " ")

    # Inject any pre-fetched data directly into the prompt so Claude can
    # answer data questions in one pass without a tool call round-trip
    data_context = ""
    if _prefetch_cache:
        parts = []
        if "calendar" in _prefetch_cache:
            parts.append(f"Google Calendar (next 7 days):\n{_prefetch_cache['calendar']}")
        if "tasks" in _prefetch_cache:
            parts.append(f"Google Tasks (open):\n{_prefetch_cache['tasks']}")
        if "emails" in _prefetch_cache:
            parts.append(f"Gmail (important unread):\n{_prefetch_cache['emails']}")
        if "weather" in _prefetch_cache:
            parts.append(f"Current weather:\n{_prefetch_cache['weather']}")
        if parts:
            data_context = (
                f"\n\nCurrent data (already fetched, use this directly without calling tools):\n"
                + "\n\n".join(parts)
            )

    memory_context = _prefetch_cache.get("memory", "") if _prefetch_cache else ""
    memory_block = (
        f"\n\nWhat you already know about {config.USER_NAME} from past conversations "
        f"(use naturally, don't recite this list — and don't state anything here as fact if the "
        f"current data above contradicts it):\n{memory_context}"
        if memory_context else ""
    )

    return (
        f"You are {config.ASSISTANT_NAME}, an AI assistant with a personality in the vein of "
        f"Tony Stark's JARVIS — dry wit, understated confidence, genuinely helpful. You are "
        f"responding to a voice command from {config.USER_NAME}. Keep responses to 1-2 sentences "
        f"maximum — this is spoken audio, brevity is essential. Never repeat yourself or "
        f"restate what you just did at the end of a response. "
        f"Never use markdown, bullet points, lists, or headers — this will be spoken aloud. "
        f"Respond directly and conversationally. "
        f"Current date and time: {now_str}. Use this to resolve relative dates/times "
        f"like 'tomorrow' or 'next Tuesday at 3pm' into exact values. "
        f"You have tools for web search, opening browsers, opening apps, fetching data, "
        f"managing the user's Google Calendar and Google Tasks (add/edit/delete events, "
        f"add/edit/complete/delete tasks), and taking/analyzing a screenshot of the user's "
        f"screen. "
        f"If the data context below already contains what you need, answer directly from it "
        f"without calling any tools — this is faster. Only call tools for fresh web searches "
        f"or if the pre-fetched data doesn't cover what was asked. "
        f"When creating or editing calendar events, always format start_datetime/end_datetime "
        f"as ISO 8601 with the same UTC offset shown in the current date and time above — "
        f"never omit the offset. "
        f"CRITICAL SAFETY RULE: before calling edit_calendar_event, delete_calendar_event, "
        f"edit_task, or delete_task, you must first respond with a short spoken question "
        f"confirming exactly what you're about to change or delete, and NOT call the tool in "
        f"that same response. Only call the tool on the user's next turn, and only if they "
        f"clearly say yes/confirm/do it — if they decline or say something else, do not call "
        f"the tool. This safety check does not apply to add_calendar_event, add_task, or "
        f"complete_task, which can be called directly. "
        f"When opening apps, use open_app with the closest match from: {app_list}. "
        f"Speak one brief sentence confirming what you opened. Nothing more."
        f"{data_context}"
        f"{memory_block}"
    )


def is_briefing_request(text: str) -> bool:
    text_lower = text.lower()
    keywords = [
        "morning briefing", "daily briefing", "my briefing",
        "morning update", "run the briefing", "start the briefing",
        "give me my briefing", "morning summary", "daily summary",
        "warning briefing", "morning brief", "daily brief",
        "run briefing", "start briefing", "launch briefing",
        "morning report", "daily report", "my morning",
        # "mourning" is a true homophone of "morning" — Whisper can't
        # tell them apart by sound alone
        "mourning briefing", "mourning update", "mourning brief",
        "mourning summary", "mourning report",
        "give me a briefing", "give me the briefing", "brief me",
    ]
    return any(kw in text_lower for kw in keywords)


def launch_briefing():
    import subprocess as _sp2, threading as _t2, sys as _sys2
    project_dir = os.path.dirname(os.path.abspath(__file__))
    _t2.Thread(
        target=lambda: _sp2.run(
            [_sys2.executable, '-u', 'briefing.py', '--force'],
            cwd=project_dir
        ),
        daemon=False
    ).start()


def wait_for_briefing_and_clear(active_event, max_wait_seconds: float = 240):
    """
    Polls the launched briefing subprocess's local dashboard server
    (localhost:8420/api/state) and clears active_event once the briefing
    has actually finished — or after max_wait_seconds if something goes
    wrong, so wake-word listening can never get stuck suppressed forever.

    The subprocess's whole process (dashboard server included) exits once
    the briefing completes, rather than settling into a steady "idle"
    state — confirmed by testing against a real run. So completion is
    detected as: it responded before, and now it doesn't.
    """
    import requests

    deadline = time.time() + max_wait_seconds
    time.sleep(3)  # give the subprocess a moment to start its dashboard server
    ever_connected = False
    while time.time() < deadline:
        try:
            resp = requests.get("http://localhost:8420/api/state", timeout=2)
            ever_connected = True
            if resp.json().get("status") == "idle":
                break
        except Exception:
            if ever_connected:
                break  # was running, now unreachable — process finished and exited
            # else: hasn't started yet, keep waiting
        time.sleep(2)
    active_event.clear()


def acknowledgment_phrase() -> str:
    """Returns a varied acknowledgment so it doesn't feel repetitive."""
    import random
    phrases = [
        "What can I do for you, sir?",
        "How can I help?",
        "Yes, sir?",
        "At your service.",
        "What do you need?",
        "Go ahead, sir.",
    ]
    return random.choice(phrases)


def listen_loop(whisper_model):
    """
    Main always-on listening loop. Continuously records short chunks,
    transcribes them, and checks for the wake word. When detected,
    checks if you kept talking immediately:
      - If yes (spoke within 1 second) → skip acknowledgment, process command directly
      - If no (paused after saying Vader) → acknowledge first, then listen for command
    Supports sleep/wake voice commands.
    """
    import threading

    print(f"\n[Vader] Listening for wake word — say 'Vader' or 'Hey Vader'\n")

    sleeping = False
    # Set while a launched briefing subprocess is still actively speaking —
    # suppresses wake-word listening entirely so the briefing's own audio
    # (picked up via mic bleed) can't falsely re-trigger a new conversation.
    briefing_active_event = threading.Event()

    while True:
        try:
            audio_chunk = record_chunk(WAKE_CHUNK_SECONDS)
            text = transcribe(audio_chunk, whisper_model)

            if text:
                print(f"[heard] {text}")

            if briefing_active_event.is_set():
                continue

            if sleeping:
                if contains_wake_word(text) and is_wake_command(text):
                    sleeping = False
                    print("[Vader] Waking up...")
                    speak.speak("Good to be back, sir.")
                    print(f"\n[Vader] Listening for wake word — say 'Vader' or 'Hey Vader'\n")
                continue

            if not contains_wake_word(text):
                continue

            print(f"\n[Vader] Wake word detected!")

            # Pre-fetch all four data sources in parallel the moment the
            # wake word is detected — runs while you're still speaking your
            # command, so data is ready by the time Claude needs it.
            import threading
            import concurrent.futures

            global _prefetch_cache, _prefetch_thread
            _prefetch_cache = {}

            def _prefetch():
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                    futures = {
                        ex.submit(get_calendar_events, 7): "calendar",
                        ex.submit(get_tasks): "tasks",
                        ex.submit(get_emails): "emails",
                        ex.submit(get_current_weather): "weather",
                        ex.submit(memory.get_memory_context): "memory",
                    }
                    for future, key in futures.items():
                        try:
                            _prefetch_cache[key] = future.result(timeout=8)
                        except Exception as e:
                            _prefetch_cache[key] = f"Could not fetch {key}: {e}"

            _prefetch_thread = threading.Thread(target=_prefetch, daemon=True)
            _prefetch_thread.start()

            # Play chime in a background thread so recording starts immediately
            # — this means if you keep talking right after "Vader", we catch
            # your full sentence without waiting for the chime to finish first.
            threading.Thread(target=play_chime, daemon=True).start()

            print("[Vader] Listening for your command...")

            # Single recording pass — starts immediately. If you keep talking
            # right away, it waits for you to finish (silence-based cutoff
            # below). If you go quiet for 1 second without saying anything,
            # it gives up and moves straight to the acknowledgment prompt.
            command_audio, spoke_immediately = record_command(initial_wait_seconds=1.0)
            command_text = transcribe(command_audio, whisper_model)

            command_clean = command_text.lower().strip().strip('.,!')
            is_just_wakeword = command_clean in (
                [""] + WAKE_WORDS + [f"hey {w}" for w in WAKE_WORDS] + [f"okay {w}" for w in WAKE_WORDS]
            )

            if not spoke_immediately or is_just_wakeword or not command_text.strip():
                # Nothing said within 1 second — acknowledge and wait
                ack = acknowledgment_phrase()
                print(f"[Vader] {ack}")
                speak.speak(ack)
                print("[Vader] Listening...")
                command_audio, _ = record_command(initial_wait_seconds=2.5)
                command_text = transcribe(command_audio, whisper_model)

            if not command_text or len(command_text.strip()) < 3:
                print("[Vader] Didn't catch that, resuming.\n")
                continue

            # Strip any wake words that bled into the command text to
            # prevent the response triggering another wake detection cycle
            command_text_clean = command_text
            for word in WAKE_WORDS:
                command_text_clean = command_text_clean.lower().replace(word, "").strip()
            if len(command_text_clean) > 3:
                command_text = command_text_clean

            print(f"[Vader] You said: {command_text}")

            if is_sleep_command(command_text):
                sleeping = True
                speak.speak("Going to sleep, sir. Say 'Vader, wake up' when you need me.")
                print("[Vader] Sleeping — say 'Vader, wake up' to resume.\n")
                continue

            if is_briefing_request(command_text):
                print("[Vader] Launching morning briefing...")
                speak.speak("Starting your morning briefing now, sir.")
                launch_briefing()
                briefing_active_event.set()
                threading.Thread(
                    target=wait_for_briefing_and_clear, args=(briefing_active_event,), daemon=True
                ).start()
                print("[Vader] Briefing is playing — wake word ignored until it finishes.\n")
                continue

            if is_thanks(command_text):
                print("[Vader] Heard a thank you — responding instantly.")
                play_thanks_response()
                print(f"\n[Vader] Listening for wake word — say 'Vader' or 'Hey Vader'\n")
                time.sleep(0.8)
                continue

            print("[Vader] Thinking...")
            conversation_history = []
            play_filler()
            response = speak_streaming_response(command_text, conversation_history)
            print(f"[Vader] {response}\n")

            # Build history for follow-up context
            conversation_history.append({"role": "user", "content": command_text})
            conversation_history.append({"role": "assistant", "content": response})

            # Stay in conversation mode — wait 2.5 seconds for a follow-up
            # before dropping back to wake word listening
            while True:
                print("[Vader] Waiting for follow-up (2.5 seconds)...")
                followup_audio, detected = record_followup(wait_seconds=2.5)

                if not detected:
                    print("[Vader] Conversation ended, resuming wake word listening.\n")
                    break

                followup_text = transcribe(followup_audio, whisper_model)
                if not followup_text or len(followup_text.strip()) < 3:
                    print("[Vader] Didn't catch that, ending conversation.\n")
                    break

                print(f"[Vader] You said: {followup_text}")

                if is_sleep_command(followup_text):
                    sleeping = True
                    speak.speak("Going to sleep, sir. Say 'Vader, wake up' when you need me.")
                    print("[Vader] Sleeping — say 'Vader, wake up' to resume.\n")
                    break

                if is_briefing_request(followup_text):
                    print("[Vader] Launching morning briefing...")
                    speak.speak("Starting your morning briefing now, sir.")
                    launch_briefing()
                    briefing_active_event.set()
                    threading.Thread(
                        target=wait_for_briefing_and_clear, args=(briefing_active_event,), daemon=True
                    ).start()
                    break

                if is_thanks(followup_text):
                    print("[Vader] Heard a thank you — responding instantly.")
                    play_thanks_response()
                    break

                print("[Vader] Thinking...")
                play_filler()
                followup_response = speak_streaming_response(followup_text, conversation_history)
                print(f"[Vader] {followup_response}\n")

                # Add to history so context builds across the whole conversation
                conversation_history.append({"role": "user", "content": followup_text})
                conversation_history.append({"role": "assistant", "content": followup_response})

            # Extract any durable facts from this conversation in the background —
            # conversation_history is about to be discarded either way, and this
            # can take a second or two without anyone noticing since Vader has
            # already finished responding.
            threading.Thread(
                target=memory.extract_and_store, args=(conversation_history,), daemon=True
            ).start()

            time.sleep(0.8)  # Cooldown so Vader's own voice doesn't re-trigger wake detection
            print(f"\n[Vader] Listening for wake word — say 'Vader' or 'Hey Vader'\n")

        except KeyboardInterrupt:
            print("\n[Vader] Shutting down.")
            break
        except Exception as e:
            print(f"[Vader] Error: {e} — continuing.")
            time.sleep(0.5)

    close_mic_stream()


def main():
    print("=" * 50)
    print(f"  {config.ASSISTANT_NAME} Voice Listener")
    print("=" * 50)

    whisper_model = load_whisper()
    open_mic_stream()
    memory.init_db()
    discover_apps()
    generate_filler_cache()
    generate_thanks_cache()
    listen_loop(whisper_model)


if __name__ == "__main__":
    main()
