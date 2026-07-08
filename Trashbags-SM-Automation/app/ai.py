"""Generates on-brand replies with Claude, with a strict latency fallback (Req 3).

Key behaviours:
  - Feeds the product knowledge base into a cached system prompt (cheap + fast on
    repeat messages).
  - Returns structured output: reply text + a confidence score + a needs_human flag.
  - If the AI is down or slower than AI_TIMEOUT_SECONDS, returns a friendly
    "we'll get back to you shortly" holding message so the customer never gets silence.
"""

import asyncio
import random
import time

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from .config import get_settings
from .knowledge_base import load_product_info


class AIReply(BaseModel):
    """The structured shape we ask Claude to return."""
    reply_text: str = Field(description="The reply to send the customer, in the owner's casual voice. Short, DM length. No hyphens or dashes. Leave this EMPTY ONLY if this is a business/brand collaboration inquiry from an account with 5000 or more followers (see BUSINESS COLLAB rule) — every other case, including a business collab under 5000 followers, gets a normal reply.")
    confidence: float = Field(description="0.0-1.0: how confident you are this reply is correct.")
    needs_human: bool = Field(description="True for: (1) an INDIVIDUAL asking about the affiliate program/sponsorship whose follower count is known and is over 2000, (2) a BUSINESS COLLAB inquiry with a known follower count of 5000+, or (3) a BUSINESS COLLAB inquiry with a known follower count under 5000 (flagged but not urgent — see BUSINESS COLLAB rule). False otherwise — including any case where follower count is unknown.")
    reason: str = Field(default="", description="If needs_human is true, note the person's @handle, follower count, and page focus. Add the word URGENT only if they have over 2000 followers (individual) or 5000+ followers (business collab). For a business collab under 5000 followers, instead note it's below the program threshold (not urgent).")


class AIResult(BaseModel):
    """What this module returns to the rest of the app."""
    reply_text: str
    confidence: float
    needs_human: bool
    reason: str
    model: str
    latency_ms: int
    fallback_used: bool


SYSTEM_TEMPLATE = """You are the customer-service assistant for Trashbags (trashbagsworld.com), a brand known for baggy, oversized snow pants and streetwear. You reply to customer DMs on Instagram.

VOICE (you ARE the owner, replying personally in your DMs — match this voice):
- Super casual and hyped, like texting a friend. You ride/ski and you're stoked on the gear.
- Common openers, varied (do NOT use one every single time): "what's up dawg!", "what up dude!", "hey whats up dawg".
- Use his slang naturally, don't force it: dawg, dude, lmk, bc, imma, peep, cop (means buy), lowkey, fresh, "they run big", "rocked" (means wore).
- Relaxed grammar and contractions; casual lowercase is fine. Keep it short, DM length. A little hype is good (e.g. "15k!!!").
- Do NOT use hyphens or dashes.

ANSWERING:
- Use ONLY the brand info below. Keep it accurate; don't make things up.
- Sizing: the pants RUN BIG. Use the height chart (all sizes fit all waists), ask their height if they haven't said, and tell them to size down or go true to size. You can point them to the size chart in the IG highlights. Want it baggy = true to size; want it less baggy = size down.
- If you cannot fully answer, or for returns, refunds, exchanges, order problems, damaged or wrong items, shipping issues, or complaints: do not make promises or guess. Send them to email help@trashbagsworld.com. He says it like "have you reached out to help@trashbagsworld.com yet? thats the best way to reach us about order stuff, we answer there same day." Do NOT flag these for a human.

AFFILIATE / SPONSORSHIP (the ONLY thing a human handles):
- SENDER INFO: every message begins with a [SENDER INFO] block showing the sender's username and follower count, pulled automatically from the Meta API. Always use that for handle/follower count. NEVER ask the customer for their Instagram handle or follower count, even if SENDER INFO is missing or shows 0 followers — just answer their question without asking.
- INDIVIDUAL asking about the affiliate program, sponsorship, being an ambassador or team rider, or getting free gear to promote (i.e. they're a person, not another business/brand): always share the affiliate page (https://trashbagsworld.com/pages/affiliate-program) and briefly mention there is a tiered program they can apply to, regardless of follower count.
  - Set needs_human to true ONLY if their follower count is known (from SENDER INFO, or stated by them in the conversation) AND is over 2000. In 'reason', note their @handle, follower count, page focus, and the word URGENT.
  - If their follower count is unknown (no SENDER INFO and they haven't stated it), or is 2000 or under, set needs_human to FALSE — do not flag it, do not mark urgent. Just send the affiliate page reply. Once their follower count becomes known later (via Meta API or them stating it) and it's over 2000, flag that later message as needs_human true.
- BUSINESS COLLAB: if the message is from another business, brand, page, or company (not an individual) proposing a collab, partnership, or business opportunity:
  - If their follower count is known and is 5000 or more: do NOT reply at all — leave reply_text EMPTY. Set needs_human to true so the owner reviews it personally. In 'reason', note their @handle, follower count, page focus, and the word URGENT.
  - If their follower count is known and is UNDER 5000: still send a normal friendly reply (e.g. acknowledge interest, ask what they have in mind). ALSO set needs_human to true so the owner sees it, but do NOT mark it urgent — in 'reason', note their @handle, follower count, page focus, and that they're below the 5000 follower threshold for the program.
  - If their follower count is unknown: send a normal friendly reply and do NOT flag it (needs_human false) — we can't assess them without a follower count yet.
- Never tell a customer the follower requirements or whether they qualify. The owner decides that.

--- BRAND INFORMATION ---
{product_info}
--- END BRAND INFORMATION ---"""


_EMOJI_INTERVAL = 9  # one emoji per every ~9 bot replies (within the 8-10 target range)


def _allow_emoji(bot_message_count: int) -> bool:
    """True on every 9th outgoing bot reply — keeps emoji rare but natural."""
    return bot_message_count > 0 and (bot_message_count % _EMOJI_INTERVAL) == 0


_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    return _client


def _build_system() -> list[dict]:
    text = SYSTEM_TEMPLATE.format(product_info=load_product_info())
    # cache_control caches this frozen prompt+knowledge-base prefix, so repeated
    # DMs are cheaper and faster to answer.
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


async def generate_reply(
    history: list[dict],
    user_message: str,
    sender_profile: dict | None = None,
    bot_message_count: int = 0,
) -> AIResult:
    """Ask Claude for a reply; fall back to a holding message on timeout/error.

    sender_profile (optional): dict with 'username' and 'follower_count' fetched
    from the Instagram Graph API. When provided, it's prepended to the message so
    Claude can apply affiliate thresholds without asking the customer.
    """
    settings = get_settings()
    start = time.monotonic()
    try:
        reply: AIReply = await asyncio.wait_for(
            _call_model(history, user_message, sender_profile=sender_profile,
                        allow_emoji=_allow_emoji(bot_message_count)),
            timeout=settings.ai_timeout_seconds,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        # Only affiliate/sponsorship inquiries route to a human now; the AI decides
        # that via needs_human. Everything else is answered or sent to support email.
        return AIResult(
            reply_text=reply.reply_text,
            confidence=reply.confidence,
            needs_human=reply.needs_human,
            reason=reply.reason,
            model=settings.ai_model,
            latency_ms=latency_ms,
            fallback_used=False,
        )
    except Exception as exc:  # timeout, API error, parse failure — anything
        latency_ms = int((time.monotonic() - start) * 1000)
        return AIResult(
            reply_text=settings.holding_message,
            confidence=0.0,
            needs_human=False,  # an AI outage isn't a human-takeover; just send the holding line
            reason=f"AI fallback ({type(exc).__name__}: {exc})",
            model=settings.ai_model,
            latency_ms=latency_ms,
            fallback_used=True,
        )


def _build_sender_prefix(profile: dict | None) -> str:
    """Build a short context block the AI reads before the customer's message.

    Injecting this per-message (not in the system prompt) so the cached system
    prompt stays shared across all conversations.
    """
    if not profile:
        return ""
    username = profile.get("username", "")
    follower_count = profile.get("follower_count", 0)
    handle = f"@{username}" if username else "unknown handle"
    return f"[SENDER INFO: {handle}, {follower_count:,} followers]\n"


async def _call_model(
    history: list[dict],
    user_message: str,
    sender_profile: dict | None = None,
    allow_emoji: bool = False,
) -> AIReply:
    settings = get_settings()
    client = _get_client()
    # Prepend sender info so the AI knows who it's talking to before it reads
    # the message. JSON.stringify in the browser or the webhook parser already
    # handles any special characters; we're just prepending a plain-text block.
    prefix = _build_sender_prefix(sender_profile)
    augmented_message = prefix + user_message if prefix else user_message
    messages = history + [{"role": "user", "content": augmented_message}]
    emoji_instruction = (
        "EMOJI: You MAY use one emoji at the end of this reply (e.g. 🤙 👍 😎 🖤 or :))."
        if allow_emoji else
        "EMOJI: Do NOT use any emoji in this reply."
    )
    system = _build_system() + [{"type": "text", "text": emoji_instruction}]
    # Opus 4.8 doesn't use extended thinking by default, which keeps replies fast.
    # output_format constrains the response to our AIReply schema.
    response = await client.messages.parse(
        model=settings.ai_model,
        max_tokens=settings.ai_max_tokens,
        system=system,
        messages=messages,
        output_format=AIReply,
    )
    if response.parsed_output is None:
        raise ValueError("Model returned no parseable structured reply")
    return response.parsed_output
