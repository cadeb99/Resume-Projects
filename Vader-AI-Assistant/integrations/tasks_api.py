"""
Google Tasks integration.
DEMO_MODE returns dummy tasks. Real mode will use the Google Tasks API.
"""

import config


def get_open_tasks():
    """Returns a list of open/incomplete tasks as dicts."""
    if config.DEMO_MODE:
        return _dummy_tasks()

    from googleapiclient.discovery import build
    from integrations.google_auth import get_credentials

    creds = get_credentials()
    service = build("tasks", "v1", credentials=creds)

    results = service.tasks().list(tasklist="@default", showCompleted=False).execute()
    raw_tasks = results.get("items", [])

    tasks = []
    for t in raw_tasks:
        due_raw = t.get("due")
        tasks.append({
            "id": t["id"],
            "title": t.get("title", "(Untitled task)"),
            "due": _format_due_date(due_raw) if due_raw else "No due date",
        })
    return tasks


def create_task(title: str, due: str = None, notes: str = "") -> dict:
    """Creates a new task in the default Google Tasks list.
    due, if given, should be an ISO 8601 date string (e.g. '2026-07-05')."""
    from googleapiclient.discovery import build
    from integrations.google_auth import get_credentials

    creds = get_credentials()
    service = build("tasks", "v1", credentials=creds)

    body = {"title": title, "notes": notes}
    if due:
        body["due"] = due
    created = service.tasks().insert(tasklist="@default", body=body).execute()
    return {"id": created["id"], "title": title}


def update_task(task_id: str, title: str = None, due: str = None, notes: str = None) -> dict:
    """Edits an existing task. Only the fields passed in are changed;
    fields left as None keep their current value."""
    from googleapiclient.discovery import build
    from integrations.google_auth import get_credentials

    creds = get_credentials()
    service = build("tasks", "v1", credentials=creds)

    task = service.tasks().get(tasklist="@default", task=task_id).execute()
    if title is not None:
        task["title"] = title
    if notes is not None:
        task["notes"] = notes
    if due is not None:
        task["due"] = due

    updated = service.tasks().update(tasklist="@default", task=task_id, body=task).execute()
    return {"id": updated["id"], "title": updated.get("title", "")}


def complete_task(task_id: str) -> dict:
    """Marks a task as completed."""
    from googleapiclient.discovery import build
    from integrations.google_auth import get_credentials

    creds = get_credentials()
    service = build("tasks", "v1", credentials=creds)

    task = service.tasks().get(tasklist="@default", task=task_id).execute()
    task["status"] = "completed"
    updated = service.tasks().update(tasklist="@default", task=task_id, body=task).execute()
    return {"id": updated["id"], "title": updated.get("title", "")}


def delete_task(task_id: str) -> None:
    """Permanently deletes a task."""
    from googleapiclient.discovery import build
    from integrations.google_auth import get_credentials

    creds = get_credentials()
    service = build("tasks", "v1", credentials=creds)
    service.tasks().delete(tasklist="@default", task=task_id).execute()


def _format_due_date(due_raw: str) -> str:
    """Formats a Google Tasks due date (ISO format) as Today/Tomorrow/date.

    Google Tasks due dates are stored as midnight UTC. Converting that
    to local time before extracting the date avoids a bug where a task
    due "today" could shift to "yesterday" depending on timezone —
    instead we treat the UTC date as the intended calendar date directly,
    since Google Tasks due dates don't carry a meaningful time-of-day."""
    from datetime import datetime as dt

    # Take the date portion as-is from the UTC value, without converting
    # to local time first — Tasks due dates are date-only by intent
    # (midnight UTC is just how Google encodes "this calendar date").
    due_date = dt.fromisoformat(due_raw.replace("Z", "+00:00")).date()
    today = dt.now().date()

    if due_date == today:
        return "Today"
    if (due_date - today).days == 1:
        return "Tomorrow"
    if due_date < today:
        return f"Overdue ({due_date.strftime('%b %d')})"
    return due_date.strftime("%b %d")


def _dummy_tasks():
    return [
        {"title": "Finish Lightspeed product mapping for 50 SKUs", "due": "Today"},
        {"title": "Send Trashbags dummy dashboard mockup", "due": "Today"},
        {"title": "Update resume with Zapier automation project", "due": "This week"},
        {"title": "Review snowpants ad report for last weekend", "due": "This week"},
    ]
