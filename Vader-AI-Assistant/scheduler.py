"""
Scheduling logic — decides whether the briefing should run right now.

Strategy: rather than fighting OS sleep/wake reliability, this is designed
to be triggered on every login/unlock event (cheap, fires often) and then
self-gates based on two conditions:
  1. Is it currently inside the configured briefing window?
  2. Has today's briefing already run?

This means you can wire it to "run on every unlock" in Task Scheduler /
launchd and trust it to only actually speak once — at the first unlock
that falls within config.BRIEFING_WINDOW_START/END each day. Voice-triggered
briefings (asking Vader directly) bypass this gate entirely via --force.

Also handles daily song selection from config.BACKGROUND_MUSIC_PLAYLIST,
ensuring the same song never plays two days in a row.
"""

import json
import os
import random
from datetime import datetime, time as dtime
import config


def _ensure_state_dir():
    os.makedirs(config.STATE_DIR, exist_ok=True)


def _read_state():
    if not os.path.exists(config.LAST_RUN_FILE):
        return {}
    try:
        with open(config.LAST_RUN_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_state(data: dict):
    _ensure_state_dir()
    with open(config.LAST_RUN_FILE, "w") as f:
        json.dump(data, f)


def _read_last_run():
    return _read_state().get("last_run_date")


def _write_last_run(date_str: str):
    state = _read_state()
    state["last_run_date"] = date_str
    _write_state(state)


def should_run_now(now: datetime = None) -> bool:
    """
    Returns True if the briefing should run right now:
    - current time falls within [BRIEFING_WINDOW_START, BRIEFING_WINDOW_END], AND
    - it hasn't already run today.

    Combined with launchd firing on every login plus every 15 minutes,
    this makes the briefing run once at the first startup/check-in of the
    day that lands inside the window. If the device isn't used at all
    during the window on a given day, it simply doesn't run that day —
    this is a window, not a "run after this time no matter how late" gate.
    """
    now = now or datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    if _read_last_run() == today_str:
        return False

    start_h, start_m = map(int, config.BRIEFING_WINDOW_START.split(":"))
    end_h, end_m = map(int, config.BRIEFING_WINDOW_END.split(":"))
    window_start = dtime(hour=start_h, minute=start_m)
    window_end = dtime(hour=end_h, minute=end_m)

    return window_start <= now.time() <= window_end


def mark_ran_today(now: datetime = None):
    """Records that the briefing has run today, so it won't fire again."""
    now = now or datetime.now()
    _write_last_run(now.strftime("%Y-%m-%d"))


def pick_todays_song() -> dict:
    """
    Picks a song from config.BACKGROUND_MUSIC_PLAYLIST at random,
    ensuring it's never the same as yesterday's pick. Returns a dict
    with 'path' and 'volume' keys so each song can have its own volume.

    Playlist entries can be either:
      - A string (path only, uses global BACKGROUND_MUSIC_VOLUME)
      - A dict with 'path' and optional 'volume' keys

    Falls back to config.BACKGROUND_MUSIC_PATH if no playlist is
    configured (backwards compatibility with single-song setup).
    """
    playlist = getattr(config, "BACKGROUND_MUSIC_PLAYLIST", [])

    if not playlist:
        return {
            "path": getattr(config, "BACKGROUND_MUSIC_PATH", ""),
            "volume": config.BACKGROUND_MUSIC_VOLUME,
        }

    def normalize(entry):
        """Convert string or dict entry to a consistent dict format."""
        if isinstance(entry, str):
            return {"path": entry, "volume": config.BACKGROUND_MUSIC_VOLUME}
        return {
            "path": entry.get("path", ""),
            "volume": entry.get("volume", config.BACKGROUND_MUSIC_VOLUME),
        }

    normalized = [normalize(e) for e in playlist]

    if len(normalized) == 1:
        return normalized[0]

    last_song = _read_state().get("last_song", "")
    available = [e for e in normalized if e["path"] != last_song]

    if not available:
        available = normalized

    chosen = random.choice(available)

    state = _read_state()
    state["last_song"] = chosen["path"]
    _write_state(state)

    return chosen


def reset_state():
    """Useful for testing — clears the last-run record entirely."""
    if os.path.exists(config.LAST_RUN_FILE):
        os.remove(config.LAST_RUN_FILE)
