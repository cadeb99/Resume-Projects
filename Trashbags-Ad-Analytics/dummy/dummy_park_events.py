# dummy/dummy_park_events.py — fake regional/grassroots event data, merged with the
# real-world recurring "big events" catalog (Olympics, World Cup, X Games, Freeride
# World Tour, Red Bull, brand events) from big_events.py so the demo report shows
# the full mix of mega, major, and grassroots events with accurate dates.
import random
from datetime import datetime, timedelta, date
from big_events import get_big_events

EVENT_TYPES = ["Slopestyle", "Halfpipe", "Rail Jam", "Big Air", "Park Opener", "Invitational"]

# Smaller, regional/grassroots events — made up for demo purposes, but modeled on
# the kind of local rail jams and resort-hosted comps that run every season.
GRASSROOTS_EVENTS_POOL = [
    {
        "name": "Corralco Slopestyle Open",
        "location": "Corralco Chile",
        "hemisphere": "southern",
        "type": "Slopestyle",
        "host": "Corralco Resort",
        "tier": "major",
        "audience": "Park Riders 16-28, South American ski community",
        "expected_attendance": random.randint(1500, 3500),
    },
    {
        "name": "Cardrona Spring Rail Jam",
        "location": "Cardrona NZ",
        "hemisphere": "southern",
        "type": "Rail Jam",
        "host": "Cardrona Alpine Resort",
        "tier": "grassroots",
        "audience": "Park Riders 18-24, NZ/AU riders, grassroots community",
        "expected_attendance": random.randint(800, 2000),
    },
    {
        "name": "Laax Rail Jam",
        "location": "Laax Switzerland",
        "hemisphere": "northern",
        "type": "Rail Jam",
        "host": "Laax Resort",
        "tier": "grassroots",
        "audience": "Park Riders 18-35, European ski market, streetwear crossover",
        "expected_attendance": random.randint(800, 2000),
    },
    {
        "name": "Perisher Big Air Series",
        "location": "Perisher NSW",
        "hemisphere": "southern",
        "type": "Big Air",
        "host": "Perisher Resort",
        "tier": "major",
        "audience": "Park Riders 16-30, Australian riders, ski enthusiasts",
        "expected_attendance": random.randint(2000, 5000),
    },
    {
        "name": "Park City Invitational Rail Jam",
        "location": "Park City UT",
        "hemisphere": "northern",
        "type": "Rail Jam",
        "host": "Park City Mountain Resort",
        "tier": "grassroots",
        "audience": "Park Riders 16-26, grassroots, local community",
        "expected_attendance": random.randint(500, 1500),
    },
    {
        "name": "Whistler Park Opener Festival",
        "location": "Whistler BC",
        "hemisphere": "northern",
        "type": "Park Opener",
        "host": "Whistler Blackcomb",
        "tier": "grassroots",
        "audience": "Park Riders 18-28, resort skiers, BC community",
        "expected_attendance": random.randint(1000, 3000),
    },
    {
        "name": "Mammoth Unbound Rail Jam",
        "location": "Mammoth CA",
        "hemisphere": "northern",
        "type": "Rail Jam",
        "host": "Mammoth Mountain",
        "tier": "grassroots",
        "audience": "Park Riders 16-24, grassroots core scene",
        "expected_attendance": random.randint(400, 1200),
    },
    {
        "name": "Breckenridge Mardi Gras Rail Jam",
        "location": "Breckenridge CO",
        "hemisphere": "northern",
        "type": "Rail Jam",
        "host": "Breckenridge Resort",
        "tier": "grassroots",
        "audience": "Park Riders 16-26, festival crowd, lifestyle crossover",
        "expected_attendance": random.randint(600, 1800),
    },
    {
        "name": "Jackson Hole Total Throwdown Rail Jam",
        "location": "Jackson Hole WY",
        "hemisphere": "northern",
        "type": "Rail Jam",
        "host": "Jackson Hole Mountain Resort",
        "tier": "grassroots",
        "audience": "Park Riders 16-28, core local scene",
        "expected_attendance": random.randint(400, 1000),
    },
    {
        "name": "Bariloche Rail Jam",
        "location": "Bariloche Argentina",
        "hemisphere": "southern",
        "type": "Rail Jam",
        "host": "Cerro Catedral Resort",
        "tier": "grassroots",
        "audience": "Park Riders 16-26, South American grassroots scene",
        "expected_attendance": random.randint(300, 900),
    },
]


def _build_grassroots_event(event: dict, today: date) -> dict:
    days_out = random.randint(5, 60)
    event_date = today + timedelta(days=days_out)
    return {
        **event,
        "event_date": event_date.strftime("%Y-%m-%d"),
        "days_until": days_out,
        "within_3_weeks": days_out <= 21,
        "advance_planning": False,
        "recommended_ad_window_start": (event_date - timedelta(days=18)).strftime("%Y-%m-%d"),
        "recommended_ad_window_end": (event_date + timedelta(days=7)).strftime("%Y-%m-%d"),
        "post_event_retargeting_end": (event_date + timedelta(days=14)).strftime("%Y-%m-%d"),
        "attendance_note": None,
    }


def get_data() -> dict:
    today = date.today()

    # Grassroots/regional events — sampled, random near-term dates
    n_grassroots = random.randint(4, 6)
    selected = random.sample(GRASSROOTS_EVENTS_POOL, n_grassroots)
    grassroots_events = [_build_grassroots_event(e, today) for e in selected]

    # Ensure at least 1 southern and 1 northern grassroots event
    hemispheres = {e["hemisphere"] for e in grassroots_events}
    if "southern" not in hemispheres:
        south_event = next(e for e in GRASSROOTS_EVENTS_POOL if e["hemisphere"] == "southern")
        grassroots_events[0] = _build_grassroots_event(south_event, today)

    # Big/brand events — Olympics, World Cup, X Games, Freeride World Tour, Red Bull,
    # brand-hosted events — real recurring calendar windows, computed relative to today
    big_events = get_big_events(today=today)

    all_events = grassroots_events + big_events
    upcoming_3w = [e for e in all_events if e["within_3_weeks"]]
    advance_planning = [e for e in all_events if e.get("advance_planning")]

    return {
        "source": "park_events",
        "status": "ok",
        "retrieved_at": datetime.utcnow().isoformat(),
        "events": sorted(all_events, key=lambda x: x["days_until"]),
        "upcoming_within_3_weeks": upcoming_3w,
        "advance_planning_needed": advance_planning,
        "total_events_found": len(all_events),
    }
