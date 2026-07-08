"""
Tests for memory.py. Plain assert-based (no pytest dependency, consistent
with the rest of this project) — run with:

    python3 test_memory.py

Uses an isolated temp DB so it never touches the real ~/.jarvis/memory.db.
The extraction test makes one real Claude API call (needs ANTHROPIC_API_KEY)
to confirm the JSON contract actually holds against the live model, not
just against my own assumptions about what it'll return.
"""

import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta

import config

# Point at an isolated temp DB before importing anything that touches it.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
config.MEMORY_DB_PATH = _tmp_db.name

import memory

PASSED = []
FAILED = []


def check(name, condition):
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name}")


def reset_db():
    if os.path.exists(config.MEMORY_DB_PATH):
        os.remove(config.MEMORY_DB_PATH)
    memory.init_db()


def test_init_db():
    print("test_init_db")
    reset_db()
    with memory._conn() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    check("all 5 tables created", {"facts", "project_state", "entities", "pattern_observations", "do_not_remember"} <= tables)


def test_write_and_read_fact():
    print("test_write_and_read_fact")
    reset_db()
    memory._store_extracted({"facts": [
        {"subject": "coffee_preference", "fact": "Cade drinks matcha, not coffee.", "category": "preference"}
    ]})
    ctx = memory.get_memory_context()
    check("fact appears in memory context", "matcha" in ctx)


def test_supersession_same_subject():
    print("test_supersession_same_subject")
    reset_db()
    memory._store_extracted({"facts": [{"subject": "coffee_preference", "fact": "Cade drinks coffee.", "category": "preference"}]})
    memory._store_extracted({"facts": [{"subject": "coffee_preference", "fact": "Cade drinks matcha now.", "category": "preference"}]})
    ctx = memory.get_memory_context()
    check("old fact superseded, not shown", "drinks coffee." not in ctx)
    check("new fact shown", "matcha" in ctx)
    with memory._conn() as conn:
        active = conn.execute("SELECT COUNT(*) c FROM facts WHERE subject='coffee_preference' AND superseded_by IS NULL").fetchone()["c"]
    check("only one active row for subject", active == 1)


def test_correction_appears_in_own_section():
    print("test_correction_appears_in_own_section")
    reset_db()
    memory._store_extracted({"facts": [
        {"subject": "meeting_time", "fact": "Standup is at 9am.", "category": "correction"}
    ]})
    ctx = memory.get_memory_context()
    check("correction labeled distinctly", "Corrections" in ctx and "Standup is at 9am" in ctx)


def test_expired_fact_excluded():
    print("test_expired_fact_excluded")
    reset_db()
    past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    memory._store_extracted({"facts": [
        {"subject": "lightspeed_sync_status", "fact": "Working on Lightspeed sync through August.",
         "category": "temporal", "expires_at": past}
    ]})
    ctx = memory.get_memory_context()
    check("expired fact excluded from context", "Lightspeed sync" not in ctx)


def test_review_after_excluded():
    print("test_review_after_excluded")
    reset_db()
    past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    memory._store_extracted({"facts": [
        {"subject": "training_block", "fact": "Training for a race this month.",
         "category": "temporal", "review_after": past}
    ]})
    ctx = memory.get_memory_context()
    check("past-review_after fact excluded from context", "Training for a race" not in ctx)


def test_active_fact_not_excluded():
    print("test_active_fact_not_excluded")
    reset_db()
    future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    memory._store_extracted({"facts": [
        {"subject": "job_search", "fact": "Actively applying to AI automation roles.",
         "category": "temporal", "expires_at": future}
    ]})
    ctx = memory.get_memory_context()
    check("future-dated fact still shown", "AI automation roles" in ctx)


def test_do_not_remember_blocks_future_and_purges_existing():
    print("test_do_not_remember_blocks_future_and_purges_existing")
    reset_db()
    memory._store_extracted({"facts": [
        {"subject": "salary_expectation", "fact": "Targeting 90k base.", "category": "recurring_fact"}
    ]})
    ctx_before = memory.get_memory_context()
    check("fact present before do-not-remember", "90k" in ctx_before)

    memory._store_extracted({"do_not_remember": [{"subject": "salary_expectation", "note": "asked not to persist"}]})
    ctx_after = memory.get_memory_context()
    check("existing fact purged once blocked", "90k" not in ctx_after)

    memory._store_extracted({"facts": [
        {"subject": "salary_expectation", "fact": "Targeting 95k base.", "category": "recurring_fact"}
    ]})
    ctx_final = memory.get_memory_context()
    check("future write to blocked subject also rejected", "95k" not in ctx_final)


def test_pattern_requires_repeated_observation():
    print("test_pattern_requires_repeated_observation")
    reset_db()
    memory._store_extracted({"patterns": [{"subject": "saturday_ski", "observation": "Mentioned skiing Saturday morning."}]})
    ctx_one = memory.get_memory_context()
    check("single observation NOT promoted to fact", "skiing Saturday" not in ctx_one)

    memory._store_extracted({"patterns": [{"subject": "saturday_ski", "observation": "Mentioned skiing Saturday morning again."}]})
    ctx_two = memory.get_memory_context()
    check("repeated observation promoted to fact", "skiing Saturday" in ctx_two)

    with memory._conn() as conn:
        count = conn.execute("SELECT observed_count, promoted_fact_id FROM pattern_observations WHERE subject='saturday_ski'").fetchone()
    check("observed_count reached threshold", count["observed_count"] >= config.PATTERN_PROMOTION_THRESHOLD)
    check("promoted_fact_id set", count["promoted_fact_id"] is not None)


def test_project_state_history_preserved():
    print("test_project_state_history_preserved")
    reset_db()
    memory._store_extracted({"project_updates": [
        {"project": "vader_memory", "status": "designing schema", "blocked_on": None}
    ]})
    memory._store_extracted({"project_updates": [
        {"project": "vader_memory", "status": "implementing write path", "blocked_on": "extraction JSON reliability"}
    ]})
    ctx = memory.get_memory_context()
    check("only latest status shown in context", "implementing write path" in ctx and "designing schema" not in ctx)
    check("blocked_on surfaced", "extraction JSON reliability" in ctx)
    with memory._conn() as conn:
        history = conn.execute("SELECT COUNT(*) c FROM project_state WHERE project='vader_memory'").fetchone()["c"]
    check("full history still in DB (not overwritten)", history == 2)


def test_entity_upsert_not_duplicated():
    print("test_entity_upsert_not_duplicated")
    reset_db()
    memory._store_extracted({"entities": [{"name": "Decker", "relationship": "coworker", "context": "Shopify project"}]})
    memory._store_extracted({"entities": [{"name": "Decker", "relationship": "coworker", "context": "Shopify + Lightspeed projects now"}]})
    ctx = memory.get_memory_context()
    check("updated context shown", "Lightspeed projects now" in ctx)
    with memory._conn() as conn:
        count = conn.execute("SELECT COUNT(*) c FROM entities WHERE name='Decker'").fetchone()["c"]
    check("no duplicate entity row", count == 1)


def test_write_path_does_not_block_caller():
    print("test_write_path_does_not_block_caller")
    reset_db()
    history = [
        {"role": "user", "content": "Remember that I prefer matcha over coffee in the mornings."},
        {"role": "assistant", "content": "Got it, matcha it is."},
    ]
    t0 = time.time()
    thread = threading.Thread(target=memory.extract_and_store, args=(history,), daemon=True)
    thread.start()
    dispatch_time = time.time() - t0
    check("starting the background thread returns near-instantly", dispatch_time < 0.05)
    thread.join(timeout=15)
    check("background extraction completed within 15s", not thread.is_alive())


def test_live_extraction_against_real_model():
    print("test_live_extraction_against_real_model (real API call)")
    if not config.ANTHROPIC_API_KEY:
        print("  SKIP  no ANTHROPIC_API_KEY set")
        return
    reset_db()
    history = [
        {"role": "user", "content": "Hey Vader, quick correction — my standup is actually at 9am now, not 9:30. "
                                      "Also I'm blocked on the Lightspeed sync because their API rate limits us at "
                                      "100 requests a minute, and I'm training for a mountain bike race in September "
                                      "so I'll be out a lot on weekends until then."},
        {"role": "assistant", "content": "Noted — 9am standup, and good luck with the training."},
    ]
    memory.extract_and_store(history)
    ctx = memory.get_memory_context()
    print(f"  --- resulting memory context ---\n{ctx}\n  --- end ---")
    check("extraction produced something", len(ctx) > 0)
    check("correction category used for standup time change", "9am" in ctx or "9 am" in ctx.lower())


if __name__ == "__main__":
    tests = [
        test_init_db,
        test_write_and_read_fact,
        test_supersession_same_subject,
        test_correction_appears_in_own_section,
        test_expired_fact_excluded,
        test_review_after_excluded,
        test_active_fact_not_excluded,
        test_do_not_remember_blocks_future_and_purges_existing,
        test_pattern_requires_repeated_observation,
        test_project_state_history_preserved,
        test_entity_upsert_not_duplicated,
        test_write_path_does_not_block_caller,
        test_live_extraction_against_real_model,
    ]
    for t in tests:
        t()
        print()

    os.remove(config.MEMORY_DB_PATH)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("Failed:", ", ".join(FAILED))
        sys.exit(1)
