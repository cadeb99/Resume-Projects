"""Logs every message, AI response, and error to a local SQLite database (Req 6).

SQLite needs zero setup and is perfect for a proof of concept. For production
you'd point this at PostgreSQL, but the table shapes stay the same.
"""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import get_settings

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    """One shared connection, created (with tables) on first use."""
    global _conn
    if _conn is None:
        path = Path(get_settings().database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL;")  # safer concurrent reads/writes
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            sender_id     TEXT PRIMARY KEY,
            paused        INTEGER NOT NULL DEFAULT 0,
            paused_reason TEXT,
            updated_at    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id  TEXT NOT NULL,
            direction  TEXT NOT NULL,          -- 'incoming' or 'outgoing'
            text       TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ai_responses (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id     TEXT NOT NULL,
            reply_text    TEXT,
            confidence    REAL,
            needs_human   INTEGER,
            model         TEXT,
            latency_ms    INTEGER,
            fallback_used INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS errors (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            context    TEXT NOT NULL,
            detail     TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


# --- Writes ---------------------------------------------------------------

def log_message(sender_id: str, direction: str, text: str) -> None:
    conn = get_connection()
    with _lock:
        conn.execute(
            "INSERT INTO messages (sender_id, direction, text, created_at) VALUES (?, ?, ?, ?)",
            (sender_id, direction, text, _now()),
        )
        conn.commit()


def log_ai_response(sender_id, reply_text, confidence, needs_human,
                    model, latency_ms, fallback_used) -> None:
    conn = get_connection()
    with _lock:
        conn.execute(
            """INSERT INTO ai_responses
               (sender_id, reply_text, confidence, needs_human, model,
                latency_ms, fallback_used, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (sender_id, reply_text, confidence, int(needs_human), model,
             latency_ms, int(fallback_used), _now()),
        )
        conn.commit()


def log_error(context: str, detail: str) -> None:
    conn = get_connection()
    with _lock:
        conn.execute(
            "INSERT INTO errors (context, detail, created_at) VALUES (?, ?, ?)",
            (context, detail, _now()),
        )
        conn.commit()


def pause_conversation(sender_id: str, reason: str) -> None:
    """Mark a conversation as human-handled so the bot stops replying (Req 5)."""
    conn = get_connection()
    with _lock:
        conn.execute(
            """INSERT INTO conversations (sender_id, paused, paused_reason, updated_at)
               VALUES (?, 1, ?, ?)
               ON CONFLICT(sender_id) DO UPDATE SET
                   paused=1, paused_reason=excluded.paused_reason, updated_at=excluded.updated_at""",
            (sender_id, reason, _now()),
        )
        conn.commit()


def resume_conversation(sender_id: str) -> None:
    """Hand a conversation back to the bot once the human is done."""
    conn = get_connection()
    with _lock:
        conn.execute(
            "UPDATE conversations SET paused=0, paused_reason=NULL, updated_at=? WHERE sender_id=?",
            (_now(), sender_id),
        )
        conn.commit()


# --- Reads ----------------------------------------------------------------

def outgoing_message_count(sender_id: str) -> int:
    """Count how many bot replies have been sent in this conversation."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM messages WHERE sender_id=? AND direction='outgoing'",
        (sender_id,),
    ).fetchone()
    return row["cnt"] if row else 0


def is_paused(sender_id: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT paused FROM conversations WHERE sender_id=?", (sender_id,)
    ).fetchone()
    return bool(row and row["paused"])


def recent_history(sender_id: str, limit: int = 10) -> list[dict]:
    """Recent turns as Claude-style messages (oldest first) for conversation context."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT direction, text FROM messages WHERE sender_id=? ORDER BY id DESC LIMIT ?",
        (sender_id, limit),
    ).fetchall()
    history = []
    for row in reversed(rows):
        role = "user" if row["direction"] == "incoming" else "assistant"
        history.append({"role": role, "content": row["text"]})
    return history


def list_conversations() -> list[dict]:
    """Every chat we've seen (one 'folder' per customer), newest activity first.

    Derived from the messages table so even chats that were never paused show up;
    the conversations table is LEFT JOINed only for the human-takeover status.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT m.sender_id                  AS sender_id,
               COUNT(*)                     AS message_count,
               MAX(m.created_at)            AS last_at,
               COALESCE(c.paused, 0)        AS paused,
               c.paused_reason              AS paused_reason
        FROM messages m
        LEFT JOIN conversations c ON c.sender_id = m.sender_id
        GROUP BY m.sender_id
        ORDER BY last_at DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def conversation_timeline(sender_id: str) -> list[dict]:
    """One chat as a single time-ordered feed: customer messages, bot replies, and
    the AI's decision (confidence / flagged / fallback) on each — for the dashboard."""
    conn = get_connection()
    events: list[dict] = []

    for m in conn.execute(
        "SELECT direction, text, created_at FROM messages WHERE sender_id=? ORDER BY id",
        (sender_id,),
    ).fetchall():
        events.append({
            "kind": m["direction"],            # 'incoming' or 'outgoing'
            "text": m["text"],
            "created_at": m["created_at"],
        })

    for a in conn.execute(
        """SELECT confidence, needs_human, fallback_used, latency_ms, created_at
           FROM ai_responses WHERE sender_id=? ORDER BY id""",
        (sender_id,),
    ).fetchall():
        events.append({
            "kind": "ai",
            "confidence": a["confidence"],
            "needs_human": bool(a["needs_human"]),
            "fallback_used": bool(a["fallback_used"]),
            "latency_ms": a["latency_ms"],
            "created_at": a["created_at"],
        })

    events.sort(key=lambda e: e["created_at"])
    return events
