"""
Google Calendar integration.
DEMO_MODE returns dummy events. Real mode will use the Google Calendar API
once OAuth credentials are configured.
"""

from datetime import datetime, timedelta
import config


def get_todays_events():
    """Returns a list of today's calendar events as dicts."""
    if config.DEMO_MODE:
        return _dummy_events()

    from googleapiclient.discovery import build
    from integrations.google_auth import get_credentials

    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)

    # Use LOCAL time for day boundaries — using UTC here would shift
    # "today" by several hours depending on timezone, potentially
    # missing early-morning events or pulling in the wrong day's events
    # near midnight.
    now_local = datetime.now().astimezone()
    start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=start_of_day.isoformat(),
        timeMax=end_of_day.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    raw_events = events_result.get("items", [])
    events = []
    for e in raw_events:
        start_raw = e["start"].get("dateTime", e["start"].get("date"))
        end_raw = e["end"].get("dateTime", e["end"].get("date"))
        events.append({
            "title": e.get("summary", "(No title)"),
            "start": _format_event_time(start_raw),
            "end": _format_event_time(end_raw),
        })
    return events


def get_upcoming_events(days_ahead: int = 7) -> list:
    """Returns upcoming events for the next N days, including each
    event's Google Calendar ID — needed to later edit or delete a
    specific event."""
    if config.DEMO_MODE:
        return _dummy_events()

    from googleapiclient.discovery import build
    from integrations.google_auth import get_credentials

    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)

    now_local = datetime.now().astimezone()
    end = now_local + timedelta(days=days_ahead)

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now_local.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=20,
    ).execute()

    raw_events = events_result.get("items", [])
    events = []
    for e in raw_events:
        start_raw = e["start"].get("dateTime", e["start"].get("date"))
        end_raw = e["end"].get("dateTime", e["end"].get("date"))
        events.append({
            "id": e["id"],
            "title": e.get("summary", "(No title)"),
            "start": start_raw,
            "end": end_raw,
        })
    return events


def create_event(title: str, start_datetime: str, end_datetime: str, description: str = "",
                  all_day: bool = False) -> dict:
    """Creates a new event on the primary Google Calendar.

    For timed events (all_day=False, the default), start_datetime/
    end_datetime must be ISO 8601 strings with a UTC offset (e.g.
    '2026-07-02T15:00:00-06:00').

    For all-day events (all_day=True), pass plain dates (e.g.
    '2026-07-04'). end_datetime is the LAST day the event covers,
    inclusive — Google's API wants an exclusive end date under the
    hood, so that's handled here automatically."""
    from googleapiclient.discovery import build
    from integrations.google_auth import get_credentials

    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)

    if all_day:
        start_field = {"date": start_datetime[:10]}
        end_field = {"date": _next_day(end_datetime[:10])}
    else:
        start_field = {"dateTime": start_datetime}
        end_field = {"dateTime": end_datetime}

    event = {
        "summary": title,
        "description": description,
        "start": start_field,
        "end": end_field,
    }
    created = service.events().insert(calendarId="primary", body=event).execute()
    return {"id": created["id"], "title": title, "start": start_datetime, "end": end_datetime}


def update_event(event_id: str, title: str = None, start_datetime: str = None,
                  end_datetime: str = None, description: str = None, all_day: bool = False) -> dict:
    """Edits an existing event. Only the fields passed in are changed;
    fields left as None keep their current value. Pass all_day=True if
    start_datetime/end_datetime are plain dates rather than datetimes
    (see create_event for the date-handling details)."""
    from googleapiclient.discovery import build
    from integrations.google_auth import get_credentials

    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)

    event = service.events().get(calendarId="primary", eventId=event_id).execute()
    if title is not None:
        event["summary"] = title
    if description is not None:
        event["description"] = description
    if start_datetime is not None:
        event["start"] = {"date": start_datetime[:10]} if all_day else {"dateTime": start_datetime}
    if end_datetime is not None:
        event["end"] = {"date": _next_day(end_datetime[:10])} if all_day else {"dateTime": end_datetime}

    updated = service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
    return {"id": updated["id"], "title": updated.get("summary", "")}


def _next_day(date_str: str) -> str:
    """Adds one day to a 'YYYY-MM-DD' string — Google Calendar's
    all-day events use an exclusive end date, one day past the last
    day the event actually covers."""
    return (datetime.fromisoformat(date_str) + timedelta(days=1)).strftime("%Y-%m-%d")


def delete_event(event_id: str) -> None:
    """Permanently deletes an event from the primary Google Calendar."""
    from googleapiclient.discovery import build
    from integrations.google_auth import get_credentials

    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)
    service.events().delete(calendarId="primary", eventId=event_id).execute()


def _format_event_time(raw_time: str) -> str:
    """Formats an ISO datetime (or date-only, for all-day events) for speech."""
    try:
        dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return "All day"


def _dummy_events():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        {
            "title": "Client call: Trashbags DM automation review",
            "start": (today + timedelta(hours=10)).strftime("%I:%M %p"),
            "end": (today + timedelta(hours=10, minutes=30)).strftime("%I:%M %p"),
        },
        {
            "title": "Lightspeed product export — sync with coworker",
            "start": (today + timedelta(hours=13)).strftime("%I:%M %p"),
            "end": (today + timedelta(hours=14)).strftime("%I:%M %p"),
        },
        {
            "title": "Gym",
            "start": (today + timedelta(hours=17, minutes=30)).strftime("%I:%M %p"),
            "end": (today + timedelta(hours=18, minutes=30)).strftime("%I:%M %p"),
        },
    ]
