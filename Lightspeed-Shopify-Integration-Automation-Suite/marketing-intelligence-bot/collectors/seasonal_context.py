"""
Summit County, CO local calendar context for the Frisco storefront (Stork &
Bear Co. / Around the World Toys). Per the store owner: this is a toy/kids-
clothing retailer, not a ski-gear shop — the busiest windows are the
**holiday shopping season (late Nov through end of Jan)** and **mid-summer**,
not ski season specifically. Modeled directly on that, not generic ski-town
seasonality.
"""
from datetime import date

# (month, day) start/end, inclusive. Straddles year boundary for holiday season.
HOLIDAY_SEASON = {"start": (11, 24), "end": (1, 31)}   # Black Friday/Thanksgiving week through end of Jan (holiday gifting + post-holiday/birthday shopping)
MIDSUMMER_SEASON = {"start": (6, 15), "end": (8, 15)}   # peak summer tourist + family travel window

# Category -> season(s) it should be boosted in
CATEGORY_SEASON_BOOST = {
    "winter_outerwear": ["holiday_season"],
    "footwear": ["holiday_season", "midsummer_season"],
    "outdoor_toys": ["midsummer_season"],
    "gifts_novelty": ["holiday_season", "midsummer_season"],  # tourists buy gifts whenever they visit
    "educational_toys_games": ["holiday_season"],               # top holiday gift category
    "books_crafts": ["holiday_season"],
    "plush_collectibles": ["holiday_season", "midsummer_season"],  # easy tourist grab-and-go gift
    "everyday_clothing": [],  # steady year-round, no strong seasonal signal
    "baby_gear": [],
}

# Recurring local events worth tying content/ads to. Not exhaustive — update
# yearly. Confirmed for 2026 via SummitDaily / Dillon Amphitheater / Town of
# Dillon sources as of 2026-07; treat future years as approximate until
# re-confirmed. Kept even though this store isn't ski-focused, since these
# are real foot-traffic drivers regardless of category (locals + tourists
# both pass Main St during these).
LOCAL_EVENTS_2026 = [
    {"name": "Dillon Farmers Market", "start": date(2026, 6, 5), "end": date(2026, 9, 25),
     "recurring": "Fridays", "relevant_categories": ["gifts_novelty", "plush_collectibles"]},
    {"name": "Lake Dillon Arts Festival", "start": date(2026, 7, 18), "end": date(2026, 7, 19),
     "relevant_categories": ["gifts_novelty", "plush_collectibles", "books_crafts"]},
    {"name": "Dillon Amphitheater Summer Concert Series", "start": date(2026, 6, 1), "end": date(2026, 9, 6),
     "relevant_categories": ["gifts_novelty", "outdoor_toys"]},
    {"name": "Small Business Saturday", "start": date(2026, 11, 28), "end": date(2026, 11, 28),
     "relevant_categories": ["educational_toys_games", "plush_collectibles", "gifts_novelty", "winter_outerwear"]},
    {"name": "Holiday Gift Shopping Window", "start": date(2026, 12, 1), "end": date(2026, 12, 24),
     "relevant_categories": ["educational_toys_games", "books_crafts", "plush_collectibles", "winter_outerwear", "gifts_novelty"]},
]


def _in_window(today, window):
    start_m, start_d = window["start"]
    end_m, end_d = window["end"]
    # Handle windows that cross Jan 1 (e.g. holiday season Nov->Jan)
    if start_m > end_m:
        if today.month >= start_m:
            start = date(today.year, start_m, start_d)
            end = date(today.year + 1, end_m, end_d)
        else:
            start = date(today.year - 1, start_m, start_d)
            end = date(today.year, end_m, end_d)
    else:
        start = date(today.year, start_m, start_d)
        end = date(today.year, end_m, end_d)
    return start <= today <= end


def get_current_season(today=None):
    today = today or date.today()
    if _in_window(today, HOLIDAY_SEASON):
        return "holiday_season"
    if _in_window(today, MIDSUMMER_SEASON):
        return "midsummer_season"
    return "shoulder_season"


def get_season_boost(category, current_season=None):
    """Returns True if this category should be boosted given the current season."""
    current_season = current_season or get_current_season()
    return current_season in CATEGORY_SEASON_BOOST.get(category, [])


def get_upcoming_events(today=None, within_days=14):
    """Events starting within the next `within_days` days — for content hooks
    like 'Arts Festival this weekend, stop by after.'"""
    today = today or date.today()
    upcoming = []
    for event in LOCAL_EVENTS_2026:
        delta = (event["start"] - today).days
        if 0 <= delta <= within_days:
            upcoming.append(event)
    return upcoming
