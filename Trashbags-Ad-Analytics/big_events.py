# big_events.py — shared catalog of recurring real-world ski/snowboard events
# Single source of truth used by BOTH dummy (demo mode) and collectors (live mode),
# so the "big" calendar events (Olympics, World Cup, X Games, Freeride World Tour,
# Red Bull, brand-hosted events) stay consistent and date-accurate everywhere.
#
# Dates are computed from each event's real-world recurring month/day relative to
# "today" (rolling forward to next year if the date already passed this year).
# A small amount of jitter is applied to non-mega tiers to simulate year-to-year
# date drift (most of these events shift by a few days each season).
#
# NOTE: these are realistic recurring calendar windows based on each event's
# historical scheduling pattern, not pulled from a live official calendar feed.
# When going live, verify exact dates against each organizer's published schedule
# (FIS, ESPN X Games, Burton, Freeride World Tour, IOC) and update typical_month/
# typical_day below if an event has moved.

import random
import calendar
from datetime import date, timedelta

TIERS = ["mega", "major", "grassroots"]

# fields: name, location, hemisphere, type, host, tier, audience,
#         typical_month, typical_day, attendance_range OR attendance_note,
#         fixed_date (optional — overrides typical_month/day, used for one-off events)
BIG_EVENTS_POOL = [
    {
        "name": "Winter Olympic Games",
        "location": "French Alps, France",
        "hemisphere": "northern",
        "type": "Olympics",
        "host": "International Olympic Committee",
        "tier": "mega",
        "audience": "Global — all 3 audience pillars, biggest brand-visibility moment in the sport",
        "fixed_date": "2030-02-06",
        "attendance_note": "3+ billion global TV viewers",
        "long_range": True,
    },
    {
        "name": "X Games Aspen",
        "location": "Aspen CO",
        "hemisphere": "northern",
        "type": "X Games",
        "host": "ESPN",
        "tier": "mega",
        "audience": "Park Riders 16-34, massive broadcast + streaming reach",
        "typical_month": 1, "typical_day": 23,
        "attendance_range": (25000, 35000),
    },
    {
        "name": "FIS Alpine Ski World Cup Finals",
        "location": "Rotating Host Resort, Europe",
        "hemisphere": "northern",
        "type": "World Cup",
        "host": "FIS / Audi",
        "tier": "mega",
        "audience": "Functional Ski Market, global ski enthusiasts",
        "typical_month": 3, "typical_day": 15,
        "attendance_range": (15000, 25000),
    },
    {
        "name": "FIS Freestyle World Cup — Mammoth Slopestyle",
        "location": "Mammoth CA",
        "hemisphere": "northern",
        "type": "World Cup",
        "host": "FIS",
        "tier": "major",
        "audience": "Park Riders 16-30, competitive scene",
        "typical_month": 1, "typical_day": 10,
        "attendance_range": (4000, 7000),
    },
    {
        "name": "FIS Freestyle World Cup — Calgary WinSport Big Air",
        "location": "Calgary AB",
        "hemisphere": "northern",
        "type": "World Cup",
        "host": "FIS / WinSport",
        "tier": "major",
        "audience": "Park Riders 18-30, Canadian market, lifestyle crossover",
        "typical_month": 12, "typical_day": 13,
        "attendance_range": (5000, 9000),
    },
    {
        "name": "Freeride World Tour — Baqueira Beret",
        "location": "Baqueira Beret, Spain",
        "hemisphere": "northern",
        "type": "Freeride World Tour",
        "host": "Freeride World Tour",
        "tier": "major",
        "audience": "Functional Ski + big-mountain crossover",
        "typical_month": 1, "typical_day": 17,
        "attendance_range": (3000, 6000),
    },
    {
        "name": "Freeride World Tour — Kicking Horse",
        "location": "Kicking Horse, Canada",
        "hemisphere": "northern",
        "type": "Freeride World Tour",
        "host": "Freeride World Tour",
        "tier": "major",
        "audience": "Functional Ski Market, big-mountain riders",
        "typical_month": 2, "typical_day": 5,
        "attendance_range": (2500, 5000),
    },
    {
        "name": "Freeride World Tour — Verbier Xtreme Finals",
        "location": "Verbier, Switzerland",
        "hemisphere": "northern",
        "type": "Freeride World Tour",
        "host": "Freeride World Tour",
        "tier": "mega",
        "audience": "Functional Ski Market, global big-mountain audience",
        "typical_month": 3, "typical_day": 27,
        "attendance_range": (8000, 15000),
    },
    {
        "name": "Burton US Open Snowboarding Championships",
        "location": "Vail CO",
        "hemisphere": "northern",
        "type": "Brand Event",
        "host": "Burton",
        "tier": "mega",
        "audience": "Park Riders + Streetwear/Lifestyle crossover",
        "typical_month": 3, "typical_day": 4,
        "attendance_range": (10000, 18000),
    },
    {
        "name": "Dew Tour",
        "location": "Copper Mountain CO",
        "hemisphere": "northern",
        "type": "Brand Event",
        "host": "Dew Tour / Mountain Dew",
        "tier": "major",
        "audience": "Park Riders 16-28",
        "typical_month": 12, "typical_day": 11,
        "attendance_range": (6000, 10000),
    },
    {
        "name": "Nine Knights",
        "location": "Saalbach, Austria",
        "hemisphere": "northern",
        "type": "Brand Event",
        "host": "Quiksilver / Nine Knights",
        "tier": "major",
        "audience": "Park Riders, core snowboard culture",
        "typical_month": 1, "typical_day": 14,
        "attendance_range": (2000, 4000),
    },
    {
        "name": "Red Bull Cold Rush",
        "location": "Crested Butte CO",
        "hemisphere": "northern",
        "type": "Red Bull Event",
        "host": "Red Bull",
        "tier": "major",
        "audience": "Functional Ski Market, big-mountain riders",
        "typical_month": 2, "typical_day": 24,
        "attendance_range": (1500, 3000),
    },
    {
        "name": "Red Bull Linecatcher",
        "location": "Global Online Film Drop",
        "hemisphere": "northern",
        "type": "Red Bull Event",
        "host": "Red Bull",
        "tier": "major",
        "audience": "Streetwear/Lifestyle + Functional Ski, online-first reach",
        "typical_month": 3, "typical_day": 3,
        "attendance_note": "Online release — millions of views, no physical attendance",
    },
    {
        "name": "The North Face Masters of Snowboarding",
        "location": "Snowbird UT",
        "hemisphere": "northern",
        "type": "Brand Event",
        "host": "The North Face",
        "tier": "major",
        "audience": "Park Riders, core snowboard scene",
        "typical_month": 2, "typical_day": 11,
        "attendance_range": (1500, 3000),
    },
    {
        "name": "Volcom Peanut Butter & Rail Jam",
        "location": "Mammoth CA",
        "hemisphere": "northern",
        "type": "Brand Event",
        "host": "Volcom",
        "tier": "grassroots",
        "audience": "Park Riders 14-22, grassroots/core",
        "typical_month": 1, "typical_day": 19,
        "attendance_range": (600, 1500),
    },
    {
        "name": "Mammoth Grand Prix Slopestyle",
        "location": "Mammoth CA",
        "hemisphere": "northern",
        "type": "World Cup",
        "host": "U.S. Ski & Snowboard / Visa",
        "tier": "mega",
        "audience": "Park Riders 18-30, Olympic qualifying event",
        "typical_month": 1, "typical_day": 21,
        "attendance_range": (4000, 8000),
    },
    {
        "name": "NZ Winter Games — Cardrona Park & Pipe Open",
        "location": "Cardrona NZ",
        "hemisphere": "southern",
        "type": "World Cup",
        "host": "NZ Winter Games",
        "tier": "major",
        "audience": "Park Riders + Functional Ski, ANZ regional draw",
        "typical_month": 8, "typical_day": 19,
        "attendance_range": (2000, 4000),
    },
    {
        "name": "Australian Interschools Snowsports Championships",
        "location": "Perisher NSW",
        "hemisphere": "southern",
        "type": "Invitational",
        "host": "Australian Interschools",
        "tier": "grassroots",
        "audience": "Junior/grassroots riders, family audience",
        "typical_month": 8, "typical_day": 29,
        "attendance_range": (3000, 6000),
    },
    {
        "name": "Las Leñas Freeride Open",
        "location": "Las Leñas, Argentina",
        "hemisphere": "southern",
        "type": "Freeride World Tour",
        "host": "Freeride World Qualifier",
        "tier": "major",
        "audience": "Functional Ski Market, South American big-mountain riders",
        "typical_month": 8, "typical_day": 21,
        "attendance_range": (1000, 2500),
    },
    {
        "name": "Valle Nevado Big Mountain Open",
        "location": "Valle Nevado, Chile",
        "hemisphere": "southern",
        "type": "Invitational",
        "host": "Copa FreeSki Chile",
        "tier": "grassroots",
        "audience": "Park Riders + Functional Ski, grassroots South American scene",
        "typical_month": 9, "typical_day": 4,
        "attendance_range": (500, 1200),
    },
]


def _next_occurrence(today: date, month: int, day: int) -> date:
    """Roll a recurring month/day forward to the next future occurrence from today."""
    year = today.year
    last_day = calendar.monthrange(year, month)[1]
    candidate = date(year, month, min(day, last_day))
    if candidate < today:
        year += 1
        last_day = calendar.monthrange(year, month)[1]
        candidate = date(year, month, min(day, last_day))
    return candidate


def get_big_events(today: date = None, jitter: bool = True) -> list[dict]:
    """Return the full catalog of big/brand events with computed real dates relative to today."""
    if today is None:
        today = date.today()

    events = []
    for e in BIG_EVENTS_POOL:
        if e.get("fixed_date"):
            event_date = date.fromisoformat(e["fixed_date"])
        else:
            event_date = _next_occurrence(today, e["typical_month"], e["typical_day"])
            if jitter and not e.get("long_range"):
                spread = 2 if e["tier"] == "mega" else (4 if e["tier"] == "major" else 7)
                event_date += timedelta(days=random.randint(-spread, spread))
                if event_date < today:
                    event_date = today + timedelta(days=random.randint(1, spread))

        days_until = (event_date - today).days
        attendance = None
        if "attendance_range" in e:
            attendance = random.randint(*e["attendance_range"])

        events.append({
            "name": e["name"],
            "location": e["location"],
            "hemisphere": e["hemisphere"],
            "type": e["type"],
            "host": e["host"],
            "tier": e["tier"],
            "audience": e["audience"],
            "expected_attendance": attendance,
            "attendance_note": e.get("attendance_note"),
            "event_date": event_date.strftime("%Y-%m-%d"),
            "days_until": days_until,
            "within_3_weeks": 0 <= days_until <= 21,
            "advance_planning": e["tier"] == "mega" and days_until > 21,
            "recommended_ad_window_start": (event_date - timedelta(days=18)).strftime("%Y-%m-%d"),
            "recommended_ad_window_end": (event_date + timedelta(days=7)).strftime("%Y-%m-%d"),
            "post_event_retargeting_end": (event_date + timedelta(days=14)).strftime("%Y-%m-%d"),
        })

    return sorted(events, key=lambda x: x["days_until"])
