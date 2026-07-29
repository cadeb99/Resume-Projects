"""
Open-Meteo forecast for Dillon, CO — used to weight winter-gear vs. summer-gear
recommendations against what's actually about to happen outside this week.
Real API call, no auth required, works in both demo and live mode.
"""
import requests
import config

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather_context():
    loc = config.STORE_LOCATION
    try:
        resp = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": loc["lat"],
                "longitude": loc["lon"],
                "daily": "temperature_2m_max,temperature_2m_min,snowfall_sum",
                "temperature_unit": "fahrenheit",
                "timezone": "America/Denver",
                "forecast_days": 7,
            },
            timeout=10,
        )
        resp.raise_for_status()
        daily = resp.json()["daily"]
        avg_high = sum(daily["temperature_2m_max"]) / len(daily["temperature_2m_max"])
        total_snow = sum(daily["snowfall_sum"])
        return {
            "avg_high_f": round(avg_high, 1),
            "total_snowfall_in": round(total_snow, 1),
            "snow_expected": total_snow > 0,
            "source": "open-meteo",
        }
    except Exception:
        return {
            "avg_high_f": None,
            "total_snowfall_in": None,
            "snow_expected": False,
            "source": "unavailable",
        }
