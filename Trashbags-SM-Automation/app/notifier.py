"""Alerts the business owner (Req 5 & 7).

Defaults to printing to the console (always works). If you configure Slack or
Twilio in .env, alerts also go there — so "the server went down at 2am" can
literally text your friend.
"""

import httpx

from .config import get_settings


async def notify(subject: str, body: str) -> None:
    settings = get_settings()
    channel = settings.notify_channel.lower()

    try:
        if channel == "slack" and settings.slack_webhook_url:
            await _notify_slack(settings, subject, body)
        elif channel == "twilio" and settings.twilio_account_sid:
            await _notify_twilio(settings, subject, body)
    except Exception as exc:  # never let a failed alert crash the pipeline
        print(f"[notifier] alert delivery failed: {exc}")

    # Always log to console as a reliable backstop.
    print(f"\n🔔 ALERT for {settings.owner_name}: {subject}\n{body}\n")


async def _notify_slack(settings, subject: str, body: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(settings.slack_webhook_url, json={"text": f"*{subject}*\n{body}"})


async def _notify_twilio(settings, subject: str, body: str) -> None:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    data = {
        "From": settings.twilio_from_number,
        "To": settings.owner_phone_number,
        "Body": f"{subject}\n{body}",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, data=data, auth=(settings.twilio_account_sid, settings.twilio_auth_token))
