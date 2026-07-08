"""
Long-term memory for Vader.

Read path: get_memory_context() runs alongside calendar/tasks/email/weather
in the existing wake-word prefetch (see jarvis_listen.py's _prefetch), so it
never adds latency to a live turn — a capped, indexed SQLite read here is
sub-5ms, faster than any of the network calls it runs next to.

Write path: extract_and_store() is meant to be fired in a daemon background
thread right after a conversation ends (conversation_history is about to be
discarded anyway) — it calls Claude once to pull structured facts out of the
transcript, then writes them. Nothing here ever runs on the voice loop's
critical path.

Consolidation: consolidate() is meant to be called once a day (piggybacked
on the existing morning briefing run) to merge same-subject duplicates that
used slightly different wording across sessions — the cheap per-write
supersede logic already handles exact-subject matches; this catches the
fuzzy cases without needing an LLM call on every write.

Categories, and why each is separate:
  preference / recurring_fact — durable, no shelf life.
  correction — the user explicitly said Vader got something wrong; these
    supersede same-subject facts immediately, not just on nightly cleanup.
  pathway — a shortcut/procedure worth remembering so it isn't re-derived
    every time (e.g. "the Lightspeed export is always in the Exports folder").
  temporal — true for now but has a natural end date. Always carries
    expires_at (or at least review_after) — stale info is worse than none.
  emotional_state — sparse, short-lived situational context for tone
    matching. Always short expiry; never treated as a durable fact.
  rejected_approach — something tried and abandoned, so it isn't suggested
    again.
  routine — an inferred habit. Never written directly from one mention —
    staged in pattern_observations until seen config.PATTERN_PROMOTION_THRESHOLD
    times, then promoted into a real fact.
project/goal state and people/entities get their own tables (see schema)
since they're not "facts about Cade" so much as structured, evolving state.
do_not_remember is a hard filter on the write path, not a memory category —
matched both by exact subject and semantically (via the extraction prompt),
so a blocked topic can't sneak back in under different wording.
"""

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta

import config

_write_lock = threading.Lock()  # SQLite + multiple background threads


@contextmanager
def _conn():
    os.makedirs(os.path.dirname(config.MEMORY_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(config.MEMORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Creates all memory tables if they don't already exist. Safe to call
    on every startup."""
    with _conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY,
            subject TEXT NOT NULL,
            fact TEXT NOT NULL,
            category TEXT NOT NULL,
            expires_at TEXT,
            review_after TEXT,
            source_session_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            superseded_by INTEGER REFERENCES facts(id)
        );
        CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject);
        CREATE INDEX IF NOT EXISTS idx_facts_active ON facts(superseded_by);

        CREATE TABLE IF NOT EXISTS project_state (
            id INTEGER PRIMARY KEY,
            project TEXT NOT NULL,
            status TEXT NOT NULL,
            blocked_on TEXT,
            source_session_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_project_state_project ON project_state(project);

        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            relationship TEXT,
            context TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pattern_observations (
            id INTEGER PRIMARY KEY,
            subject TEXT NOT NULL,
            observation TEXT NOT NULL,
            observed_count INTEGER NOT NULL DEFAULT 1,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            promoted_fact_id INTEGER REFERENCES facts(id)
        );
        CREATE INDEX IF NOT EXISTS idx_pattern_subject ON pattern_observations(subject);

        CREATE TABLE IF NOT EXISTS do_not_remember (
            id INTEGER PRIMARY KEY,
            subject TEXT NOT NULL UNIQUE,
            note TEXT,
            created_at TEXT NOT NULL
        );
        """)


# =========================================================================
# Read path
# =========================================================================

def get_memory_context(max_facts: int = 20) -> str:
    """
    Returns a formatted text block of everything currently known about
    Cade, ready to drop into the system prompt. Meant to be called from
    the same prefetch thread pool as calendar/tasks/email/weather.
    """
    try:
        now = datetime.now().isoformat()
        with _conn() as conn:
            facts = conn.execute(
                """
                SELECT subject, fact, category FROM facts
                WHERE superseded_by IS NULL
                  AND (expires_at IS NULL OR expires_at > ?)
                  AND (review_after IS NULL OR review_after > ?)
                ORDER BY
                  CASE category WHEN 'correction' THEN 0 ELSE 1 END,
                  updated_at DESC
                LIMIT ?
                """,
                (now, now, max_facts),
            ).fetchall()

            projects = conn.execute(
                """
                SELECT project, status, blocked_on, source_session_at FROM project_state
                WHERE id IN (SELECT MAX(id) FROM project_state GROUP BY project)
                ORDER BY source_session_at DESC
                LIMIT 15
                """
            ).fetchall()

            entities = conn.execute(
                "SELECT name, relationship, context FROM entities ORDER BY updated_at DESC LIMIT 30"
            ).fetchall()

        if not facts and not projects and not entities:
            return ""

        parts = []

        corrections = [f for f in facts if f["category"] == "correction"]
        rejected = [f for f in facts if f["category"] == "rejected_approach"]
        other_facts = [f for f in facts if f["category"] not in ("correction", "rejected_approach")]

        if corrections:
            parts.append(
                "Corrections (trust these over anything that seems to contradict them):\n"
                + "\n".join(f"- {f['fact']}" for f in corrections)
            )
        if other_facts:
            parts.append(
                "Known facts, preferences, and pathways:\n"
                + "\n".join(f"- {f['fact']}" for f in other_facts)
            )
        if projects:
            parts.append(
                "Ongoing projects (most recent status):\n"
                + "\n".join(
                    f"- {p['project']}: {p['status']}"
                    + (f" (blocked on: {p['blocked_on']})" if p["blocked_on"] else "")
                    for p in projects
                )
            )
        if entities:
            parts.append(
                "People:\n"
                + "\n".join(
                    f"- {e['name']}" + (f" ({e['relationship']})" if e["relationship"] else "")
                    + (f" — {e['context']}" if e["context"] else "")
                    for e in entities
                )
            )
        if rejected:
            parts.append(
                "Approaches already tried and rejected — don't re-suggest these:\n"
                + "\n".join(f"- {f['fact']}" for f in rejected)
            )

        return "\n\n".join(parts)
    except Exception as e:
        return f"(memory unavailable: {e})"


# =========================================================================
# Write path
# =========================================================================

EXTRACTION_SYSTEM_PROMPT = """You extract durable memory from a voice assistant conversation transcript. \
Be conservative — most short exchanges (checking weather, opening an app, a quick question) contain \
nothing worth remembering. Only extract things that would genuinely help a future conversation.

Categories:
- preference / recurring_fact: durable facts about Cade with no natural expiration (likes, habits stated \
  as fact, standing info).
- correction: Cade explicitly said Vader got something wrong or corrected a prior assumption. These \
  override conflicting facts.
- pathway: a shortcut or procedure worth remembering so it isn't re-derived every time (e.g. "the \
  Lightspeed export is always in the Exports folder", "the fastest way to reach Decker is Slack not email").
- temporal: true right now but has a natural end (a project deadline, a training block, a season). \
  MUST include expires_at as a YYYY-MM-DD date — estimate one from context if not exact (e.g. "through \
  August" -> August 31 of the current or next occurrence of August). If you can't estimate a hard \
  expiry, set review_after instead (a date to stop confidently asserting it without confirming).
- emotional_state: brief, situational context useful for tone-matching (stressed, excited, etc). \
  ALWAYS set expires_at within a few days — these must be short-lived. Use sparingly; do not \
  editorialize or infer feelings that weren't expressed.
- rejected_approach: something Cade tried and abandoned, or a suggestion he explicitly turned down. \
  Prevents re-suggesting the same dead end.

project_updates: status of an ongoing project/goal (not a fact about Cade — the current state of \
something). Include "blocked_on" if something is blocking progress, else omit it.

entities: people Vader should recognize by name with context (role/relationship + what they're \
connected to).

patterns: a POSSIBLE routine/habit Vader noticed but Cade never explicitly stated as a rule (e.g. \
mentioning skiing Saturday morning once). Do not put confirmed, explicitly-stated facts here — those \
go in "facts" as recurring_fact instead. This is only for inferred, unconfirmed habits.

do_not_remember: Cade explicitly asked Vader not to remember or to forget something. Give a short \
subject key for what topic is now off-limits.

Respond with ONLY valid JSON, no other text, in this exact shape:
{
  "facts": [{"subject": "snake_case_key", "fact": "...", "category": "...", "expires_at": "YYYY-MM-DD or null", "review_after": "YYYY-MM-DD or null"}],
  "project_updates": [{"project": "snake_case_key", "status": "...", "blocked_on": "... or null"}],
  "entities": [{"name": "...", "relationship": "...", "context": "..."}],
  "patterns": [{"subject": "snake_case_key", "observation": "..."}],
  "do_not_remember": [{"subject": "snake_case_key", "note": "..."}]
}
Use empty arrays for anything with nothing to extract. Never invent facts not clearly supported by \
the transcript."""


def _transcript_text(conversation_history: list) -> str:
    lines = []
    for turn in conversation_history:
        role = "Cade" if turn.get("role") == "user" else config.ASSISTANT_NAME
        content = turn.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _call_extraction_model(transcript: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    blocked = _blocked_subjects()
    blocked_note = (
        f"\n\nTopics Cade has asked not to be remembered — do not propose any fact related to these, "
        f"even if worded differently: {', '.join(blocked)}"
        if blocked else ""
    )

    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=800,
        system=EXTRACTION_SYSTEM_PROMPT + blocked_note,
        messages=[{
            "role": "user",
            "content": f"Today's date: {datetime.now().strftime('%Y-%m-%d')}\n\nTranscript:\n{transcript}",
        }],
    )
    text = "".join(b.text for b in response.content if hasattr(b, "text")).strip()

    # Tolerate the model wrapping JSON in a code fence or adding stray text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {}
    return json.loads(text[start:end + 1])


def extract_and_store(conversation_history: list):
    """
    Entry point for the write path. Meant to be run in a daemon background
    thread — never call this from the main voice loop thread.
    """
    if not conversation_history:
        return
    try:
        transcript = _transcript_text(conversation_history)
        data = _call_extraction_model(transcript)
        _store_extracted(data)
    except Exception as e:
        print(f"[memory] Extraction failed, skipping this session: {e}")


def _blocked_subjects() -> list:
    with _conn() as conn:
        rows = conn.execute("SELECT subject FROM do_not_remember").fetchall()
    return [r["subject"] for r in rows]


def _store_extracted(data: dict):
    now = datetime.now().isoformat()
    session_at = now

    with _write_lock, _conn() as conn:
        blocked = {r["subject"] for r in conn.execute("SELECT subject FROM do_not_remember").fetchall()}

        for dnr in data.get("do_not_remember", []):
            subject = dnr.get("subject", "").strip()
            if not subject:
                continue
            conn.execute(
                "INSERT INTO do_not_remember (subject, note, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT(subject) DO UPDATE SET note=excluded.note",
                (subject, dnr.get("note", ""), now),
            )
            conn.execute("DELETE FROM facts WHERE subject = ?", (subject,))
            blocked.add(subject)

        for f in data.get("facts", []):
            subject = f.get("subject", "").strip()
            fact = f.get("fact", "").strip()
            if not subject or not fact or subject in blocked:
                continue
            cur = conn.execute(
                "INSERT INTO facts (subject, fact, category, expires_at, review_after, "
                "source_session_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (subject, fact, f.get("category", "recurring_fact"),
                 f.get("expires_at"), f.get("review_after"), session_at, now),
            )
            new_id = cur.lastrowid
            conn.execute(
                "UPDATE facts SET superseded_by = ? WHERE subject = ? AND id != ? AND superseded_by IS NULL",
                (new_id, subject, new_id),
            )

        for p in data.get("project_updates", []):
            project = p.get("project", "").strip()
            status = p.get("status", "").strip()
            if not project or not status:
                continue
            conn.execute(
                "INSERT INTO project_state (project, status, blocked_on, source_session_at) "
                "VALUES (?, ?, ?, ?)",
                (project, status, p.get("blocked_on"), session_at),
            )

        for e in data.get("entities", []):
            name = e.get("name", "").strip()
            if not name:
                continue
            conn.execute(
                "INSERT INTO entities (name, relationship, context, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET relationship=excluded.relationship, "
                "context=excluded.context, updated_at=excluded.updated_at",
                (name, e.get("relationship"), e.get("context"), now),
            )

        for pat in data.get("patterns", []):
            subject = pat.get("subject", "").strip()
            observation = pat.get("observation", "").strip()
            if not subject or not observation or subject in blocked:
                continue
            _observe_pattern(conn, subject, observation, session_at, now)


def _observe_pattern(conn, subject: str, observation: str, session_at: str, now: str):
    """Stages a routine observation; promotes it to a real fact once seen
    config.PATTERN_PROMOTION_THRESHOLD times."""
    existing = conn.execute(
        "SELECT id, observed_count FROM pattern_observations WHERE subject = ? AND promoted_fact_id IS NULL",
        (subject,),
    ).fetchone()

    if existing is None:
        conn.execute(
            "INSERT INTO pattern_observations (subject, observation, observed_count, "
            "first_seen_at, last_seen_at) VALUES (?, ?, 1, ?, ?)",
            (subject, observation, session_at, session_at),
        )
        return

    new_count = existing["observed_count"] + 1
    conn.execute(
        "UPDATE pattern_observations SET observed_count = ?, observation = ?, last_seen_at = ? WHERE id = ?",
        (new_count, observation, session_at, existing["id"]),
    )

    if new_count >= config.PATTERN_PROMOTION_THRESHOLD:
        cur = conn.execute(
            "INSERT INTO facts (subject, fact, category, expires_at, review_after, "
            "source_session_at, updated_at) VALUES (?, ?, 'routine', NULL, NULL, ?, ?)",
            (subject, observation, session_at, now),
        )
        conn.execute(
            "UPDATE pattern_observations SET promoted_fact_id = ? WHERE id = ?",
            (cur.lastrowid, existing["id"]),
        )


# =========================================================================
# Consolidation (daily, piggybacked on the morning briefing run)
# =========================================================================

def consolidate():
    """
    Daily maintenance: catches near-duplicate subjects that per-write exact
    matching missed (e.g. "coffee_preference" vs "morning_coffee_habit"
    written in different sessions), by asking Claude once to spot true
    duplicates among current active facts. Cheap because it only runs once
    a day, off the hot path, and only when there's more than a handful of
    facts to check.
    """
    try:
        with _conn() as conn:
            facts = conn.execute(
                "SELECT id, subject, fact FROM facts WHERE superseded_by IS NULL ORDER BY subject"
            ).fetchall()

        if len(facts) < 4:
            return  # not enough facts for duplicate subjects to be likely

        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        listing = "\n".join(f"{f['id']}: [{f['subject']}] {f['fact']}" for f in facts)

        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=500,
            system=(
                "You are given a numbered list of stored facts (id: [subject] text). Find groups that "
                "describe the SAME underlying thing under different subject keys (true duplicates or "
                "direct contradictions only — not just related topics). For each group, pick the id of "
                "the most recent/complete fact to KEEP and list the other ids to RETIRE. "
                "Respond with ONLY JSON: {\"groups\": [{\"keep\": id, \"retire\": [id, ...]}]}. "
                "If there are no true duplicates, respond {\"groups\": []}."
            ),
            messages=[{"role": "user", "content": listing}],
        )
        text = "".join(b.text for b in response.content if hasattr(b, "text")).strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1:
            return
        result = json.loads(text[start:end + 1])

        with _write_lock, _conn() as conn:
            for group in result.get("groups", []):
                keep_id = group.get("keep")
                for retire_id in group.get("retire", []):
                    if retire_id == keep_id:
                        continue
                    conn.execute(
                        "UPDATE facts SET superseded_by = ? WHERE id = ? AND superseded_by IS NULL",
                        (keep_id, retire_id),
                    )
    except Exception as e:
        print(f"[memory] Consolidation failed (non-critical, will retry tomorrow): {e}")
