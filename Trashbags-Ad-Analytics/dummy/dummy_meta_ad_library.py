# dummy/dummy_meta_ad_library.py — fake competitor ad library data
import random
from datetime import datetime, timedelta

COMPETITOR_BRANDS = [
    "RideCo Outerwear", "PowderKing Apparel", "SlopeStyle Co",
    "ArcticThread", "FreerideGear", "NorthFace Knock-off Brand",
]

ALL_MARKETS = [
    "Denver CO", "Salt Lake City UT", "Whistler BC", "Queenstown NZ",
    "Perisher NSW", "Innsbruck Austria", "Sapporo Japan", "Park City UT",
    "Jackson Hole WY", "Mammoth CA", "Bariloche Argentina", "Laax Switzerland",
    "Aspen CO", "Telluride CO", "Steamboat CO", "Cardrona NZ",
]

FORMATS = ["Reels", "Feed", "Stories", "Carousel"]

UNCOVERED_POOL = [
    "Wanaka NZ", "Flagstaff AZ", "Burlington VT", "Las Leñas Argentina",
    "Falls Creek VIC", "Chapelco Argentina", "Portillo Chile", "Corralco Chile",
]


def get_data() -> dict:
    n_brands = random.randint(3, 5)
    brands = random.sample(COMPETITOR_BRANDS, n_brands)
    competitors = []
    covered_markets = set()

    for brand in brands:
        markets = random.sample(ALL_MARKETS, random.randint(2, 4))
        covered_markets.update(markets)
        placements = random.sample(FORMATS, random.randint(1, 3))
        start_days_ago = random.randint(3, 42)
        start_date = (datetime.utcnow() - timedelta(days=start_days_ago)).strftime("%Y-%m-%d")

        competitors.append({
            "brand": brand,
            "markets": markets,
            "placements": placements,
            "creative_longevity_days": start_days_ago,
            "ad_start_date": start_date,
            "estimated_spend_tier": random.choice(["low", "medium", "high"]),
            "primary_format": random.choice(placements),
            "long_running": start_days_ago >= 21,
        })

    # Markets with zero competitor presence
    gap_markets = [m for m in UNCOVERED_POOL if m not in covered_markets]
    gap_markets += random.sample([m for m in ALL_MARKETS if m not in covered_markets], min(2, len(ALL_MARKETS)))

    return {
        "source": "meta_ad_library",
        "status": "ok",
        "retrieved_at": datetime.utcnow().isoformat(),
        "competitors": competitors,
        "competitor_gap_markets": list(set(gap_markets))[:6],
        "total_competitors_found": n_brands,
    }
