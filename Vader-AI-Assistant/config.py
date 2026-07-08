"""
Central config for the morning briefing system.
Real values get filled in once we wire up actual APIs — for now these
are placeholders so the scaffold runs end-to-end with dummy data.
"""

import os

# --- General ---
USER_NAME = "Cade"
ASSISTANT_NAME = "Vader"

# Auto-briefing fires on the first daily device startup/login that falls
# within this window (24hr format, local time) — not a fixed clock time.
BRIEFING_WINDOW_START = "05:00"
BRIEFING_WINDOW_END = "17:00"

# --- Location (for weather) ---
CITY_NAME = "Dillon, CO"
LATITUDE = 39.6325
LONGITUDE = -106.0440

# --- Google APIs (Calendar, Tasks, Gmail) ---
# Filled in once OAuth credentials are set up
GOOGLE_CREDENTIALS_PATH = os.path.expanduser("~/.jarvis/google_credentials.json")
GOOGLE_TOKEN_PATH = os.path.expanduser("~/.jarvis/google_token.json")
GMAIL_IMPORTANT_LABEL = "Briefing"  # the Gmail label you create

# --- Claude API ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# --- ElevenLabs (TTS) ---
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = "aDu5kOKn7ph7VTkZuK6r"  # pick a voice once we set this up

OPENWEATHERMAP_API_KEY = os.environ.get("OPENWEATHERMAP_API_KEY", "")

# Voice delivery tuning. All three only apply to ElevenLabs (not the
# free OS fallback voice).
#   VOICE_SPEED: 0.7 (slower) to 1.2 (faster). 1.0 is normal pace.
#   VOICE_STABILITY: 0.0 (more expressive/variable) to 1.0 (more
#     consistent/monotone). 0.5 is a good middle ground.
#   VOICE_SIMILARITY_BOOST: 0.0-1.0, how closely it sticks to the
#     original voice sample. Higher = more faithful to your recording.
VOICE_SPEED = 1.0
VOICE_STABILITY = 0.5
VOICE_SIMILARITY_BOOST = 0.75

# --- Demo mode ---
# When True, all integrations return dummy data instead of hitting real APIs.
# Lets us test the full pipeline before any credentials exist.
DEMO_MODE = False

# --- Scheduling ---
# Tracks whether today's briefing has already run, so the trigger
# (login/unlock event) can fire multiple times a day without repeating.
STATE_DIR = os.path.expanduser("~/.jarvis")
LAST_RUN_FILE = os.path.join(STATE_DIR, "last_run.json")

# --- Memory ---
MEMORY_DB_PATH = os.path.join(STATE_DIR, "memory.db")
# How many times a routine/habit must be independently observed before it's
# promoted from a staged observation into a durable fact — a single mention
# isn't a pattern.
PATTERN_PROMOTION_THRESHOLD = 2
# Add your own royalty-free/licensed audio files to assets/ and list them
# here — not included in this repo for copyright reasons.
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
BACKGROUND_MUSIC_PLAYLIST = [
    # {"path": os.path.join(ASSETS_DIR, "your-song.mp3"), "volume": 0.10},
]
BACKGROUND_MUSIC_VOLUME = 0.10
