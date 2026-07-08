# collectors/open_meteo.py — live Open-Meteo API (no API key required)
import requests
from datetime import datetime

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

BASE_URL = "https://api.open-meteo.com/v1/forecast"


def get_data() -> dict:
    """Fetch snow forecasts for ski resorts from Open-Meteo (free, no key)."""
    try:
        resort_data = []
        for resort in RESORTS:
            params = {
                "latitude": resort["lat"],
                "longitude": resort["lon"],
                "daily": "snowfall_sum,snow_depth_max,temperature_2m_max",
                "forecast_days": 7,
                "timezone": "auto",
            }
            resp = requests.get(BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("daily", {})

            snowfall_7d = sum(data.get("snowfall_sum", [0])) * 0.394  # mm → inches
            snow_depth = max(data.get("snow_depth_max", [0])) * 39.37  # m → inches
            temp_c = max(data.get("temperature_2m_max", [0]))

            if snowfall_7d >= 18:
                conditions, priority = "Excellent", "HIGH"
            elif snowfall_7d >= 6:
                conditions, priority = "Good", "MEDIUM"
            else:
                conditions, priority = "Poor", "LOW"

            resort_data.append({
                "resort": resort["name"],
                "location": resort["location"],
                "hemisphere": resort["hemisphere"],
                "lat": resort["lat"],
                "lon": resort["lon"],
                "snowfall_7d_inches": round(snowfall_7d, 1),
                "snow_depth_inches": round(snow_depth, 1),
                "temp_c": round(temp_c, 1),
                "conditions": conditions,
                "priority": priority,
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

    except Exception as e:
        return {"source": "open_meteo", "status": "error", "error": str(e), "resorts": []}
