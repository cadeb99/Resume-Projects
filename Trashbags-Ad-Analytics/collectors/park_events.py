# collectors/park_events.py — scrape FIS freestyle calendar for regional events,
# merged with the curated "big events" catalog (Olympics, World Cup, X Games,
# Freeride World Tour, Red Bull, brand-hosted events) from big_events.py.
#
# The FIS calendar page covers FIS-sanctioned World Cup/Olympic-qualifier events
# but does not list X Games, Freeride World Tour, Red Bull, or brand events (Burton,
# The North Face, Volcom, Dew Tour, etc.) — those don't publish a single scrapable
# calendar feed, so they're tracked in big_events.py using each event's known
# recurring date window. Re-verify those dates each season against the organizer's
# official schedule and update big_events.py if a date has moved.
import requests
from datetime import datetime, date
from bs4 import BeautifulSoup
from big_events import get_big_events

FIS_URL = "https://www.fis-ski.com/DB/freestyle-skiing/calendar.html"


def _scrape_fis() -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AdAnalyzer/1.0)"}
    resp = requests.get(FIS_URL, headers=headers, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events = []
    rows = soup.select("table.g-table tbody tr")
    for row in rows[:20]:
        cols = row.find_all("td")
        if len(cols) < 4:
            continue
        event_date_text = cols[0].get_text(strip=True)
        location = cols[1].get_text(strip=True)
        event_type = cols[2].get_text(strip=True)
        event_name = cols[3].get_text(strip=True)

        events.append({
            "name": event_name,
            "location": location,
            "type": event_type,
            "event_date": event_date_text,
            "host": "FIS",
            "tier": "major",
            "source": "FIS",
            "hemisphere": "southern" if any(s in location for s in ["NZ", "Australia", "Chile", "Argentina"]) else "northern",
            "audience": "Park Riders 16-35, Competitive athletes",
        })
    return events


def get_data() -> dict:
    """Pull regional FIS events live, merged with the curated big-events catalog."""
    fis_events = []
    fis_error = None
    try:
        fis_events = _scrape_fis()
    except Exception as e:
        fis_error = str(e)

    big_events = get_big_events(today=date.today())
    all_events = fis_events + big_events

    upcoming_3w = [e for e in all_events if e.get("within_3_weeks")]
    advance_planning = [e for e in all_events if e.get("advance_planning")]

    result = {
        "source": "park_events",
        "status": "ok" if not (fis_error and not big_events) else "error",
        "retrieved_at": datetime.utcnow().isoformat(),
        "events": all_events,
        "upcoming_within_3_weeks": upcoming_3w,
        "advance_planning_needed": advance_planning,
        "total_events_found": len(all_events),
    }
    if fis_error:
        result["partial_error"] = f"FIS calendar scrape failed (big events catalog still included): {fis_error}"
    return result
