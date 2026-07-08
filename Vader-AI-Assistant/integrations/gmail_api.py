"""
Gmail integration — pulls unread emails under a specific label
(config.GMAIL_IMPORTANT_LABEL) rather than the whole inbox.
"""

import config


def get_important_emails():
    """Returns a list of unread emails under the important label."""
    if config.DEMO_MODE:
        return _dummy_emails()

    from googleapiclient.discovery import build
    from integrations.google_auth import get_credentials

    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    query = f"label:{config.GMAIL_IMPORTANT_LABEL} is:unread"
    results = service.users().messages().list(userId="me", q=query).execute()
    message_refs = results.get("messages", [])

    emails = []
    for ref in message_refs:
        msg = service.users().messages().get(
            userId="me", id=ref["id"], format="metadata",
            metadataHeaders=["From", "Subject"],
        ).execute()

        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        emails.append({
            "from": _clean_sender(headers.get("From", "Unknown sender")),
            "subject": headers.get("Subject", "(No subject)"),
            "snippet": msg.get("snippet", ""),
        })
    return emails


def _clean_sender(raw_from: str) -> str:
    """Strips email address down to just the display name, e.g.
    'Jane Doe <jane@example.com>' -> 'Jane Doe'."""
    if "<" in raw_from:
        return raw_from.split("<")[0].strip().strip('"')
    return raw_from


def _dummy_emails():
    return [
        {
            "from": "Trashbags client",
            "subject": "Quick question on DM automation timeline",
            "snippet": "Hey, wanted to check if we're still on track for the fall rollout...",
        },
        {
            "from": "Lightspeed POS Support",
            "subject": "Re: API rate limit increase request",
            "snippet": "Your request has been approved, new limits active in 24 hours...",
        },
    ]
