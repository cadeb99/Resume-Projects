"""Tests for the human-takeover logic (Req 5)."""

from app.takeover import check_takeover


def test_affiliate_keyword_alone_does_not_trigger_takeover():
    # Keyword matching alone is no longer enough — only the AI's verified
    # follower-count decision (needs_human) should trigger a takeover.
    should_pause, reason = check_takeover("hey do you do affiliate deals?", ai_needs_human=False, ai_reason="")
    assert should_pause is False
    assert reason == ""


def test_ai_flag_triggers_takeover():
    should_pause, reason = check_takeover("dm me", ai_needs_human=True, ai_reason="8k followers, ski page, URGENT")
    assert should_pause is True
    assert reason == "8k followers, ski page, URGENT"


def test_normal_message_does_not_trigger():
    should_pause, reason = check_takeover("Do you ship to Texas?", ai_needs_human=False, ai_reason="")
    assert should_pause is False
    assert reason == ""


def test_refund_does_not_trigger_takeover():
    # Refunds now go to the support email, not a human takeover.
    should_pause, _ = check_takeover("I want a refund please", ai_needs_human=False, ai_reason="")
    assert should_pause is False


def test_sponsor_keyword_alone_does_not_trigger_takeover():
    should_pause, _ = check_takeover("I want to SPONSOR you guys", ai_needs_human=False, ai_reason="")
    assert should_pause is False
