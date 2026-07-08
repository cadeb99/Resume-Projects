"""Tests for the AI latency fallback (Req 3).

These don't call the real API — they patch the model call to simulate the AI
being down or slow, and check we fall back to the holding message.
"""

import asyncio

from app import ai


async def test_fallback_when_ai_errors(monkeypatch):
    async def boom(history, user_message):
        raise RuntimeError("API down")

    monkeypatch.setattr(ai, "_call_model", boom)
    result = await ai.generate_reply([], "hello")

    assert result.fallback_used is True
    assert result.needs_human is False  # an AI outage no longer forces a human takeover
    assert result.reply_text == ai.get_settings().holding_message


async def test_fallback_on_timeout(monkeypatch):
    async def slow(history, user_message):
        await asyncio.sleep(2)  # longer than the (patched) timeout

    monkeypatch.setattr(ai.get_settings(), "ai_timeout_seconds", 0.05)
    monkeypatch.setattr(ai, "_call_model", slow)
    result = await ai.generate_reply([], "hello")

    assert result.fallback_used is True
    assert result.reply_text == ai.get_settings().holding_message
