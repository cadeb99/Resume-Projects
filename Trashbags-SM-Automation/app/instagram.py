"""Talks to Instagram: verifies incoming webhooks and sends replies (Req 2 & 4).

send_message retries up to SEND_MAX_RETRIES times with exponential backoff, then
raises so the caller can alert the owner.

get_sender_profile looks up the sender's username and follower count from the
Graph API so the AI can apply affiliate thresholds without asking the customer.
"""

import asyncio
import hashlib
import hmac
import logging

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


class InstagramSendError(Exception):
    """Raised when a reply could not be delivered after all retries."""


def verify_signature(payload: bytes, signature_header: str | None) -> bool:
    """Verify Meta's X-Hub-Signature-256 header against the app secret (Req 2).

    This proves the webhook really came from Meta and wasn't forged.
    """
    settings = get_settings()
    if not settings.app_secret:
        # No secret configured (e.g. local testing) — skip verification.
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(settings.app_secret.encode(), payload, hashlib.sha256).hexdigest()
    received = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)


async def get_sender_profile(sender_id: str) -> dict | None:
    """Look up the sender's Instagram username and follower count via the Graph API.

    Returns a dict like {"username": "ski_jones", "follower_count": 8400} or None
    if the lookup fails (no access token configured, fake ID in /simulate mode,
    API error, or the account is private/hidden).

    Called automatically before the AI so it already knows who it's talking to
    and can apply affiliate thresholds without asking the customer.
    """
    settings = get_settings()
    if not settings.access_token:
        # No live token yet (pre-Meta-approval) — skip silently.
        return None

    url = f"https://graph.facebook.com/{settings.graph_api_version}/{sender_id}"
    params = {
        "fields": "username,follower_count,name",
        "access_token": settings.access_token,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                profile = {
                    "username": data.get("username", ""),
                    "follower_count": int(data.get("follower_count", 0)),
                    "name": data.get("name", ""),
                }
                logger.info(
                    "Sender profile fetched: @%s, %d followers",
                    profile["username"],
                    profile["follower_count"],
                )
                return profile
            else:
                logger.debug("Profile lookup returned %d: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.debug("Profile lookup failed for %s: %s", sender_id, exc)

    return None


async def send_message(recipient_id: str, text: str) -> dict:
    """Send a DM via the Graph API, retrying on failure (Req 4)."""
    settings = get_settings()
    url = f"https://graph.facebook.com/{settings.graph_api_version}/me/messages"
    params = {"access_token": settings.access_token}
    body = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }

    last_error = "unknown error"
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, settings.send_max_retries + 1):
            try:
                resp = await client.post(url, params=params, json=body)
                if resp.status_code == 200:
                    return resp.json()
                last_error = f"HTTP {resp.status_code}: {resp.text}"
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"

            if attempt < settings.send_max_retries:
                await asyncio.sleep(2 ** (attempt - 1))  # 1s, then 2s, ...

    raise InstagramSendError(
        f"Failed after {settings.send_max_retries} attempts. Last error: {last_error}"
    )
