"""
Lead Follow-Up Automation - Proof of Concept
----------------------------------------------
Built as a quick demo for Vector Media's Tech Specialist role.

The idea: when a new inbound lead/inquiry comes in (sales, partnership,
experiential request, etc.), this script shows how you'd automatically:
  1. Classify the lead by type/keyword
  2. Route it to the right team member
  3. Log it to a shared tracker (here: a local CSV, standing in for
     something like a Google Sheet, Airtable base, or CRM)
  4. Send a notification (here: printed to console, standing in for
     a Slack message or email via Zapier/Make)

This is a simplified proof-of-concept using mock data - the same logic
would plug into real inputs (a web form, an inbox via Gmail API, a
webhook from a website) and real outputs (Slack API, Zapier webhook,
an actual CRM API) with no change to the core routing logic below.
"""

import csv
import os
from datetime import datetime

# --- Config: this is the part that would change per real use case ---

ROUTING_RULES = {
    "sales": {
        "keywords": ["pricing", "buy", "advertise", "campaign", "quote"],
        "owner": "National Sales Team",
    },
    "partnership": {
        "keywords": ["partner", "collaboration", "sponsorship", "brand deal"],
        "owner": "Brand Partnerships Team",
    },
    "experiential": {
        "keywords": ["event", "activation", "tour", "experiential"],
        "owner": "Experiential Team",
    },
    "support": {
        "keywords": ["issue", "help", "broken", "not working", "problem"],
        "owner": "Tech Support / Help Desk",
    },
}

LOG_FILE = os.path.join(os.path.dirname(__file__), "lead_log.csv")


def classify_lead(message_text: str) -> tuple[str, str]:
    """Look at the inbound message and figure out which team it belongs to."""
    text = message_text.lower()
    for category, rule in ROUTING_RULES.items():
        if any(keyword in text for keyword in rule["keywords"]):
            return category, rule["owner"]
    return "general", "General Inbox"


def notify_owner(owner: str, lead_name: str, category: str, message_text: str) -> None:
    """
    Stand-in for a real notification.
    In production this would be a Slack webhook, an email via Gmail API,
    or a Zapier/Make webhook - the routing logic above doesn't change either way.
    """
    print(f"[NOTIFY] -> {owner}")
    print(f"          New '{category}' lead from {lead_name}: \"{message_text[:60]}...\"")


def log_lead(lead_name: str, contact: str, category: str, owner: str, message_text: str) -> None:
    """Append the lead to a simple CSV log, standing in for a shared tracker/CRM."""
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "lead_name", "contact", "category", "owner", "message"])
        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            lead_name,
            contact,
            category,
            owner,
            message_text,
        ])


def process_lead(lead_name: str, contact: str, message_text: str) -> None:
    """Full pipeline for one inbound lead: classify -> log -> notify."""
    category, owner = classify_lead(message_text)
    log_lead(lead_name, contact, category, owner, message_text)
    notify_owner(owner, lead_name, category, message_text)
    print(f"[LOGGED] {lead_name} -> category='{category}', owner='{owner}'\n")


# --- Mock inbound leads, standing in for real form submissions/emails ---

MOCK_LEADS = [
    {
        "lead_name": "Jordan Blake",
        "contact": "jordan.blake@example.com",
        "message_text": "Hi, I'd like a quote for a transit advertising campaign in Chicago next quarter.",
    },
    {
        "lead_name": "Priya Nair",
        "contact": "priya.nair@examplebrand.com",
        "message_text": "We're interested in exploring a brand partnership / sponsorship for our sneaker launch.",
    },
    {
        "lead_name": "Sam Torres",
        "contact": "sam.torres@example.edu",
        "message_text": "Looking to set up a campus experiential activation this fall for a mobile tour.",
    },
    {
        "lead_name": "Alex Kim",
        "contact": "alex.kim@example.com",
        "message_text": "Our digital display isn't working and I need help troubleshooting it.",
    },
    {
        "lead_name": "Morgan Lee",
        "contact": "morgan.lee@example.com",
        "message_text": "Just saying hi, love the work you all do!",
    },
]


if __name__ == "__main__":
    print("=" * 60)
    print("Lead Follow-Up Automation - Demo Run")
    print("=" * 60)
    print()
    for lead in MOCK_LEADS:
        process_lead(**lead)

    print("=" * 60)
    print(f"All leads processed. Full log written to: {LOG_FILE}")
    print("=" * 60)
