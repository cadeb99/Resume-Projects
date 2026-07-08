"""
Weather integration combining three independent sources for a more
reliable consensus forecast:
  - National Weather Service (NWS) — US government source, free
  - Open-Meteo — global model-blend source, free
  - OpenWeatherMap — independent commercial provider, free tier (no
    credit card required, 1M calls/month)

Numeric values (high, low, wind, precip chance) are averaged across
whichever sources successfully respond, for a more reliable consensus
number than trusting any single source. The richest available text
(condition description, detailed notes) is kept from whichever source
provides it, preferring NWS's detailed narrative when available.

If only one or two sources respond, the average uses just those — the
whole system never fails just because one provider had an outage.

Location is auto-detected via IP geolocation each run (tries two
different providers for reliability), so it automatically follows you
if you're somewhere other than your usual location — works identically
on Mac and Windows with zero permission setup. Falls back to the
static coordinates in config.py if both lookups fail.
"""

import requests
import re
import config

NWS_USER_AGENT = "VaderBriefing/1.0 (personal automation project)"


def get_todays_weather():
    """Returns today's forecast as a dict, averaged across all weather
    sources that successfully respond. Falls back to dummy data only
    if every single source fails."""
    if config.DEMO_MODE:
        return _dummy_weather()

    lat, lon = _get_current_location()

    results = []

    nws_result = _try_nws_forecast(lat, lon)
    if nws_result:
        results.append(nws_result)

    openmeteo_result = _try_openmeteo_forecast(lat, lon)
    if openmeteo_result:
        results.append(openmeteo_result)

    openweathermap_result = _try_openweathermap_forecast(lat, lon)
    if openweathermap_result:
        results.append(openweathermap_result)

    if not results:
        print("[weather] All weather sources failed, using dummy fallback data.")
        return _dummy_weather()

    print(f"[weather] Got {len(results)}/3 source(s): "
          f"{', '.join(r['_source'] for r in results)}")

    return _reconcile_sources(results)


def _reconcile_sources(results: list) -> dict:
    """
    Averages numeric fields across all successful sources, and picks
    the richest available text fields (preferring NWS's detailed
    narrative, since the other sources don't provide one).
    """
    def avg(field):
        values = [r[field] for r in results if r.get(field) is not None]
        return round(sum(values) / len(values)) if values else None

    def avg_precise(field):
        values = [r[field] for r in results if r.get(field) is not None]
        return round(sum(values) / len(values), 1) if values else None

    # Prefer NWS's text fields since they're the most descriptive;
    # fall back to whichever other source has something.
    condition = next((r["condition"] for r in results if r["_source"] == "NWS" and r.get("condition")), None)
    if not condition:
        condition = next((r["condition"] for r in results if r.get("condition")), "mixed conditions")

    detailed_forecast = next((r.get("detailed_forecast") for r in results if r["_source"] == "NWS"), "")

    wind_direction = next((r["wind_direction"] for r in results if r["_source"] == "NWS" and r.get("wind_direction")), None)
    if not wind_direction:
        wind_direction = next((r["wind_direction"] for r in results if r.get("wind_direction")), "variable")

    gust_values = [r["wind_gust_mph"] for r in results if r.get("wind_gust_mph")]
    wind_gust_mph = max(gust_values) if gust_values else None

    return {
        "high": avg("high"),
        "low": avg("low"),
        "precip_chance": avg("precip_chance"),
        "condition": condition,
        "wind_speed_mph": avg("wind_speed_mph"),
        "wind_direction": wind_direction,
        "wind_gust_mph": wind_gust_mph,
        "detailed_forecast": detailed_forecast,
        "_sources_used": [r["_source"] for r in results],
    }


def _try_nws_forecast(lat, lon):
    """Fetches today's forecast from the National Weather Service.
    Returns None if the location is outside NWS coverage (non-US) or
    the request fails for any reason."""
    try:
        headers = {"User-Agent": NWS_USER_AGENT}

        points_resp = requests.get(
            f"https://api.weather.gov/points/{lat},{lon}", headers=headers, timeout=10
        )
        points_resp.raise_for_status()
        forecast_url = points_resp.json()["properties"]["forecast"]

        forecast_resp = requests.get(forecast_url, headers=headers, timeout=10)
        forecast_resp.raise_for_status()
        periods = forecast_resp.json()["properties"]["periods"]

        # First period is "today" (daytime high), second is typically
        # "tonight" (overnight low) — NWS structures periods this way.
        today = periods[0]
        tonight = periods[1] if len(periods) > 1 else None

        high = today["temperature"] if today["isDaytime"] else (tonight["temperature"] if tonight else today["temperature"])
        low = tonight["temperature"] if tonight and not tonight["isDaytime"] else None
        if low is None:
            low = today["temperature"]

        wind_speed_mph, wind_direction = _parse_nws_wind(today["windSpeed"], today.get("windDirection", ""))
        gust_mph = _parse_nws_gusts(today.get("detailedForecast", ""))

        return {
            "_source": "NWS",
            "high": high,
            "low": low,
            "precip_chance": today.get("probabilityOfPrecipitation", {}).get("value") or 0,
            "condition": today["shortForecast"].lower(),
            "wind_speed_mph": wind_speed_mph,
            "wind_direction": wind_direction,
            "wind_gust_mph": gust_mph,
            "detailed_forecast": today.get("detailedForecast", ""),
        }
    except Exception as e:
        print(f"[weather] NWS lookup failed: {e}")
        return None


def _parse_nws_gusts(detailed_forecast: str):
    """Extracts wind gust speed (mph) from NWS's detailedForecast text,
    e.g. 'gusts as high as 26 mph'. Returns None if no gust info is
    mentioned (calm conditions often omit it entirely)."""
    match = re.search(r'gusts? (?:as high )?as (\d+) mph', detailed_forecast, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _parse_nws_wind(wind_speed_str: str, wind_direction_raw: str):
    """
    NWS gives wind speed as a string like '10 mph' or '5 to 15 mph'
    (a range during gusty/variable conditions) and direction as an
    abbreviation like 'SW'. Parses both into a single mph number
    (using the high end of any range, since that's more relevant for
    a "how windy will it be" briefing) and a full compass word.
    """
    numbers = re.findall(r'\d+', wind_speed_str)
    speed = int(numbers[-1]) if numbers else 0

    abbreviation_map = {
        "N": "north", "NNE": "north-northeast", "NE": "northeast", "ENE": "east-northeast",
        "E": "east", "ESE": "east-southeast", "SE": "southeast", "SSE": "south-southeast",
        "S": "south", "SSW": "south-southwest", "SW": "southwest", "WSW": "west-southwest",
        "W": "west", "WNW": "west-northwest", "NW": "northwest", "NNW": "north-northwest",
    }
    direction = abbreviation_map.get(wind_direction_raw.strip().upper(), "variable")

    return speed, direction


def _try_openmeteo_forecast(lat, lon):
    """Second weather source — covers any location worldwide."""
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
            "weathercode,windspeed_10m_max,winddirection_10m_dominant"
            "&temperature_unit=fahrenheit&windspeed_unit=mph&timezone=auto"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        daily = data["daily"]
        code = daily["weathercode"][0]
        wind_dir_degrees = daily["winddirection_10m_dominant"][0]
        return {
            "_source": "Open-Meteo",
            "high": round(daily["temperature_2m_max"][0]),
            "low": round(daily["temperature_2m_min"][0]),
            "precip_chance": daily["precipitation_probability_max"][0],
            "condition": _weather_code_to_text(code),
            "wind_speed_mph": round(daily["windspeed_10m_max"][0]),
            "wind_direction": _degrees_to_compass(wind_dir_degrees),
            "wind_gust_mph": None,
        }
    except Exception as e:
        print(f"[weather] Open-Meteo lookup failed: {e}")
        return None


def _try_openweathermap_forecast(lat, lon):
    """
    Third weather source — OpenWeatherMap, using their free classic
    forecast endpoint (no credit card required, 1,000,000 calls/month
    free). This endpoint returns 3-hour interval data rather than a
    clean daily summary, so we aggregate today's remaining intervals
    into a high/low/conditions ourselves.

    Requires config.OPENWEATHERMAP_API_KEY to be set; returns None
    (silently excluded from the average) if no key is configured or
    the request fails for any reason.
    """
    if not config.OPENWEATHERMAP_API_KEY:
        return None

    try:
        url = (
            "https://api.openweathermap.org/data/2.5/forecast"
            f"?lat={lat}&lon={lon}&units=imperial&appid={config.OPENWEATHERMAP_API_KEY}"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        from datetime import datetime
        today_date = datetime.now().date()

        todays_entries = [
            entry for entry in data["list"]
            if datetime.fromtimestamp(entry["dt"]).date() == today_date
        ]
        if not todays_entries:
            # If we're querying late in the day, today's intervals may
            # have already passed — fall back to the next 8 entries
            # (roughly the next 24 hours) so we still get something.
            todays_entries = data["list"][:8]

        temps = [e["main"]["temp"] for e in todays_entries]
        high = round(max(temps))
        low = round(min(temps))

        # Use the midday-ish entry for condition/wind, since that's
        # most representative of "today" rather than early morning
        midpoint_entry = todays_entries[len(todays_entries) // 2]
        condition = midpoint_entry["weather"][0]["description"].lower()
        wind_speed_mph = round(midpoint_entry["wind"]["speed"])
        wind_direction = _degrees_to_compass(midpoint_entry["wind"].get("deg", 0))
        wind_gust_mph = round(midpoint_entry["wind"]["gust"]) if midpoint_entry["wind"].get("gust") else None

        precip_chance = round(max(e.get("pop", 0) for e in todays_entries) * 100)

        return {
            "_source": "OpenWeatherMap",
            "high": high,
            "low": low,
            "precip_chance": precip_chance,
            "condition": condition,
            "wind_speed_mph": wind_speed_mph,
            "wind_direction": wind_direction,
            "wind_gust_mph": wind_gust_mph,
        }
    except Exception as e:
        print(f"[weather] OpenWeatherMap lookup failed: {e}")
        return None


def _get_current_location():
    """
    Returns (latitude, longitude), trying progressively from most to
    least reliable automatic source, all of which work identically on
    Mac and Windows with zero permission setup:
      1. ip-api.com (primary — proven reliable, no rate limit hit in testing)
      2. ipapi.co (secondary — different provider, used if primary fails;
         note this one has hit free-tier rate limits in practice)
      3. Static config.py coordinates (final safety net)

    This automatically picks up on location changes (e.g. traveling)
    since it's based on your current IP each time the briefing runs,
    though IP-based geolocation is typically accurate to city/metro
    level rather than exact GPS precision.
    """
    location = _try_ip_api_com()
    if location:
        return location

    location = _try_ipapi_co()
    if location:
        return location

    print("[weather] All geolocation lookups failed, falling back to static configured location.")
    return config.LATITUDE, config.LONGITUDE


def _try_ipapi_co():
    """Primary IP geolocation source — generally more accurate."""
    try:
        resp = requests.get("https://ipapi.co/json/", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if "latitude" in data and "longitude" in data and not data.get("error"):
            return data["latitude"], data["longitude"]
    except Exception as e:
        print(f"[weather] ipapi.co lookup failed: {e}")
    return None


def _try_ip_api_com():
    """Secondary IP geolocation source, used if the primary fails or
    is rate-limited."""
    try:
        resp = requests.get("http://ip-api.com/json/", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            return data["lat"], data["lon"]
    except Exception as e:
        print(f"[weather] ip-api.com lookup failed: {e}")
    return None


def _degrees_to_compass(degrees: float) -> str:
    """Converts a wind direction in degrees to a compass direction
    (e.g. 'northwest') for natural speech."""
    directions = [
        "north", "north-northeast", "northeast", "east-northeast",
        "east", "east-southeast", "southeast", "south-southeast",
        "south", "south-southwest", "southwest", "west-southwest",
        "west", "west-northwest", "northwest", "north-northwest",
    ]
    index = round(degrees / 22.5) % 16
    return directions[index]


def _weather_code_to_text(code: int) -> str:
    """Translates Open-Meteo's WMO weather code into a human-readable
    condition description, so the briefing can actually describe the
    sky (sunny, cloudy, snowing, etc.) instead of just temperatures."""
    mapping = {
        0: "clear skies",
        1: "mostly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "foggy",
        48: "foggy with frost",
        51: "light drizzle",
        53: "drizzle",
        55: "heavy drizzle",
        61: "light rain",
        63: "rain",
        65: "heavy rain",
        71: "light snow",
        73: "snow",
        75: "heavy snow",
        77: "snow flurries",
        80: "light rain showers",
        81: "rain showers",
        82: "heavy rain showers",
        85: "light snow showers",
        86: "heavy snow showers",
        95: "thunderstorms",
        96: "thunderstorms with hail",
        99: "severe thunderstorms with hail",
    }
    return mapping.get(code, "mixed conditions")


def _dummy_weather():
    return {
        "high": 58,
        "low": 31,
        "precip_chance": 20,
        "condition_code": 1,  # mostly clear
        "condition": "mostly clear",
        "wind_speed_mph": 8,
        "wind_direction": "northwest",
        "wind_gust_mph": None,
        "detailed_forecast": "Mostly clear skies with light winds.",
    }
