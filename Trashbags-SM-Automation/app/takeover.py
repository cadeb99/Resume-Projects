"""Decides when to pause the bot and hand a conversation to a human (Req 5).

A conversation is flagged only when the AI itself decides it needs a human
(needs_human=True) — e.g. an affiliate/sponsorship inquiry with a verified
follower count over the threshold. We don't keyword-match on words like
"sponsor" because that flags people before their follower count is known.
"""


def check_takeover(message_text: str, ai_needs_human: bool, ai_reason: str) -> tuple[bool, str]:
    """Return (should_pause, reason)."""
    if ai_needs_human:
        return True, ai_reason or "Affiliate/sponsorship inquiry for the owner to review"
    return False, ""
