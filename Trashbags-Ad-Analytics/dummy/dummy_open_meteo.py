# dummy/dummy_open_meteo.py — fake snow conditions and weather forecasts
import random
from datetime import datetime

from ski_calendar import get_hemisphere_status

RESORTS = [
    {"name": "Whistler Blackcomb", "location": "Whistler BC", "hemisphere": "northern", "lat": 50.1, "lon": -122.9},
    {"name": "Park City Mountain", "location": "Park City UT", "hemisphere": "northern", "lat": 40.6, "lon": -111.5},
    {"name": "Mammoth Mountain", "location": "Mammoth CA", "hemisphere": "northern", "lat": 37.6, "lon": -119.0},
    {"name": "Jackson Hole", "location": "Jackson Hole WY", "hemisphere": "northern", "lat": 43.6, "lon": -110.8},
    {"name": "Aspen Snowmass", "location": "Aspen CO", "hemisphere": "northern", "lat": 39.2, "lon": -106.8},
    {"name": "Innsbruck Nordkette", "location": "Innsbruck Austria", "hemisphere": "northern", "lat": 47.3, "lon": 11.4},
    {"name": "Niseko United", "location": "Sapporo Japan", "hemisphere": "northern", "lat": 42.8, "lon": 140.7},
    {"name": "Cardrona Alpine", "location": "Cardrona NZ", "hemisphere": "southern", "lat": -44.9, "lon": 169.0},
    {"name": "Coronet Peak", "location": "Queenstown NZ", "hemisphere": "southern", "lat": -45.1, "lon": 168.8},
    {"name": "Perisher Valley", "location": "Perisher NSW", "hemisphere": "southern", "lat": -36.4, "lon": 148.4},
    {"name": "Valle Nevado", "location": "Valle Nevado Chile", "hemisphere": "southern", "lat": -33.3, "lon": -70.3},
    {"name": "Cerro Catedral", "location": "Bariloche Argentina", "hemisphere": "southern", "lat": -41.2, "lon": -71.4},
]


def get_data() -> dict:
    status = get_hemisphere_status()
    resort_data = []

    good_resorts = random.sample(RESORTS, 3)
    bad_resorts = random.sample([r for r in RESORTS if r not in good_resorts], 2)

    for resort in RESORTS:
        is_in_season = (
            (resort["hemisphere"] == "northern" and status["northern"] == "PEAK SEASON") or
            (resort["hemisphere"] == "southern" and status["southern"] == "PEAK SEASON")
        )

        if resort in good_resorts:
            snowfall_7d = round(random.uniform(18, 36), 1)
            snow_depth = random.randint(60, 120)
            conditions = "Excellent"
        elif resort in bad_resorts:
            snowfall_7d = round(random.uniform(0, 4), 1)
            snow_depth = random.randint(0, 25)
            conditions = "Poor"
        elif is_in_season:
            snowfall_7d = round(random.uniform(4, 22), 1)
            snow_depth = random.randint(20, 80)
            conditions = random.choice(["Good", "Very Good", "Fair"])
        else:
            snowfall_7d = round(random.uniform(0, 8), 1)
            snow_depth = random.randint(0, 30)
            conditions = random.choice(["Poor", "Fair", "Closed"])

        temp_c = round(random.uniform(-18, 2) if is_in_season else random.uniform(-5, 12), 1)

        resort_data.append({
            "resort": resort["name"],
            "location": resort["location"],
            "hemisphere": resort["hemisphere"],
            "lat": resort["lat"],
            "lon": resort["lon"],
            "snowfall_7d_inches": snowfall_7d,
            "snow_depth_inches": snow_depth,
            "temp_c": temp_c,
            "conditions": conditions,
            "is_in_season": is_in_season,
            "priority": "HIGH" if resort in good_resorts else ("LOW" if resort in bad_resorts else "MEDIUM"),
        })

    best = max(resort_data, key=lambda x: x["snowfall_7d_inches"])
    worst = min(resort_data, key=lambda x: x["snowfall_7d_inches"])

    return {
        "source": "open_meteo",
        "status": "ok",
        "retrieved_at": datetime.utcnow().isoformat(),
        "resorts": resort_data,
        "best_snow_resort": best["resort"],
        "worst_snow_resort": worst["resort"],
        "high_priority_resorts": [r for r in resort_data if r["priority"] == "HIGH"],
        "low_priority_resorts": [r for r in resort_data if r["priority"] == "LOW"],
    }
