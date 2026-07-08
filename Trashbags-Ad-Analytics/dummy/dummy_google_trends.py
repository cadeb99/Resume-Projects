# dummy/dummy_google_trends.py — fake Google Trends search volume data
import random
from datetime import datetime, date

from ski_calendar import NORTHERN_HEMISPHERE_TARGETS, SOUTHERN_HEMISPHERE_TARGETS, get_hemisphere_status

SEARCH_TERMS = [
    "snowpants", "ski pants baggy", "park skiing gear", "slopestyle outerwear",
    "halfpipe competition", "ski apparel", "snowboard pants", "park rider style",
    "ski fashion", "powder pants", "terrain park", "rail jam",
]

PARK_TERMS = ["halfpipe", "slopestyle", "rail jam", "big air", "park skiing"]


def get_data() -> dict:
    status = get_hemisphere_status()
    all_cities = NORTHERN_HEMISPHERE_TARGETS + SOUTHERN_HEMISPHERE_TARGETS

    city_trends = []
    spike_cities = random.sample(all_cities, random.randint(3, 5))

    for city in all_cities:
        is_north = city in NORTHERN_HEMISPHERE_TARGETS
        # Hemisphere-appropriate cities trend higher
        if is_north and status["northern"] == "PEAK SEASON":
            base_interest = random.randint(45, 85)
        elif not is_north and status["southern"] == "PEAK SEASON":
            base_interest = random.randint(45, 85)
        else:
            base_interest = random.randint(10, 45)

        wow_change = random.uniform(-20, 60) if city not in spike_cities else random.uniform(30, 60)
        current_interest = min(100, max(1, int(base_interest * (1 + wow_change / 100))))

        city_trends.append({
            "city": city,
            "current_interest": current_interest,
            "wow_change_pct": round(wow_change, 1),
            "is_spiking": wow_change >= 30,
            "hemisphere": "northern" if is_north else "southern",
        })

    # Park/event search terms
    term_trends = []
    for term in random.sample(SEARCH_TERMS, 8):
        wow = round(random.uniform(-15, 55), 1)
        term_trends.append({
            "term": term,
            "interest": random.randint(20, 90),
            "wow_change_pct": wow,
            "is_spiking": wow >= 25,
            "category": "park" if term in PARK_TERMS else "general",
        })

    spiking_cities = [c for c in city_trends if c["is_spiking"]]
    spiking_terms = [t for t in term_trends if t["is_spiking"]]

    return {
        "source": "google_trends",
        "status": "ok",
        "retrieved_at": datetime.utcnow().isoformat(),
        "city_trends": city_trends,
        "term_trends": term_trends,
        "spiking_cities": spiking_cities,
        "spiking_terms": spiking_terms,
        "top_spiking_city": max(city_trends, key=lambda x: x["wow_change_pct"])["city"],
    }
