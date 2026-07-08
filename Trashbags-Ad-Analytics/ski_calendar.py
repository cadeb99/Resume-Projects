# ski_calendar.py — global season context and target market lists
from datetime import date

NORTHERN_HEMISPHERE_TARGETS = [
    "Denver CO", "Salt Lake City UT", "Vancouver BC", "Whistler BC",
    "Innsbruck Austria", "Sapporo Japan", "Burlington VT", "Boulder CO",
    "Flagstaff AZ", "Mammoth CA", "Tahoe CA", "Park City UT",
    "Steamboat CO", "Telluride CO", "Jackson Hole WY",
    "New York City NY", "Los Angeles CA", "Tokyo Japan",
]

SOUTHERN_HEMISPHERE_TARGETS = [
    "Queenstown NZ", "Wanaka NZ", "Christchurch NZ", "Auckland NZ",
    "Perisher NSW", "Thredbo NSW", "Falls Creek VIC", "Mt Buller VIC",
    "Melbourne Australia", "Sydney Australia",
    "Bariloche Argentina", "Las Leñas Argentina", "Chapelco Argentina", "Buenos Aires Argentina",
    "Valle Nevado Chile", "El Colorado Chile", "Portillo Chile", "Santiago Chile",
]

PARK_EVENT_MARKETS = [
    "Mammoth CA", "Aspen CO", "Laax Switzerland", "Corralco Chile",
    "Cardrona NZ", "Perisher NSW", "Calgary AB",
]

STREETWEAR_MARKETS = ["New York City NY", "Los Angeles CA", "Tokyo Japan", "Melbourne Australia", "London UK"]

SEASON_CALENDAR = {
    "northern_peak": list(range(10, 13)) + list(range(1, 4)),   # Oct–Mar
    "southern_peak": list(range(6, 10)),                         # Jun–Sep
    "shoulder": [4, 5],                                           # Apr–May
}


def get_hemisphere_status() -> dict:
    """Return current season status for each hemisphere based on today's date."""
    month = date.today().month
    if month in SEASON_CALENDAR["northern_peak"]:
        north = "PEAK SEASON"
        south = "OFF SEASON"
    elif month in SEASON_CALENDAR["southern_peak"]:
        north = "OFF SEASON"
        south = "PEAK SEASON"
    else:
        north = "SHOULDER SEASON"
        south = "SHOULDER SEASON"

    return {
        "northern": north,
        "southern": south,
        "month": month,
        "is_shoulder": month in SEASON_CALENDAR["shoulder"],
    }


def get_context_string() -> str:
    status = get_hemisphere_status()
    return (
        f"SEASON CONTEXT:\n"
        f"  Northern Hemisphere: {status['northern']}\n"
        f"  Southern Hemisphere: {status['southern']}\n"
        f"  Shoulder season (target both + streetwear): {'YES' if status['is_shoulder'] else 'NO'}\n\n"
        f"NORTHERN TARGETS: {', '.join(NORTHERN_HEMISPHERE_TARGETS)}\n"
        f"SOUTHERN TARGETS: {', '.join(SOUTHERN_HEMISPHERE_TARGETS)}\n"
        f"PARK EVENT MARKETS: {', '.join(PARK_EVENT_MARKETS)}\n"
        f"STREETWEAR MARKETS: {', '.join(STREETWEAR_MARKETS)}\n"
    )
