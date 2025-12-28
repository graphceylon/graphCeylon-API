from __future__ import annotations

from datetime import datetime, date, timezone
from typing import Any, Dict, Optional, Literal

import requests
from zoneinfo import ZoneInfo

from configs.recommender_service.config import OPENWEATHER_API_KEY

TimeOfDay = Optional[Literal["morning", "afternoon", "evening"]]
COLOMBO = ZoneInfo("Asia/Colombo")


def _tod_hours(tod: TimeOfDay) -> range:
    # OpenWeather is 3-hourly; we bucket to nearest nice ranges
    if tod == "morning":
        return range(6, 12)      # 06-11
    if tod == "afternoon":
        return range(12, 18)     # 12-17
    if tod == "evening":
        return range(18, 24)     # 18-23
    return range(0, 24)          # whole day


def fetch_openweather_for_city_and_day(
    city: str,
    country: str,
    target_date: date,
    time_of_day: TimeOfDay = None,
) -> Dict[str, Any]:
    """
    Fetch 3-hourly forecast slots for a given LOCAL date in Sri Lanka time.
    IMPORTANT: Filters by Asia/Colombo local date & hour (not UTC date),
    otherwise Sri Lanka requests can lose slots around midnight.
    """
    if not OPENWEATHER_API_KEY:
        raise RuntimeError("OPENWEATHER_API_KEY not set")

    q = f"{city},{country}" if country else city

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": q, "appid": OPENWEATHER_API_KEY, "units": "metric"}

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    hours = _tod_hours(time_of_day)

    rows = []
    for item in data.get("list", []) or []:
        # timezone-aware UTC
        dt_utc = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
        # convert to Sri Lanka local
        dt_local = dt_utc.astimezone(COLOMBO)

        # filter by LOCAL requested day
        if dt_local.date() != target_date:
            continue
        # filter by LOCAL hour bucket
        if dt_local.hour not in hours:
            continue

        main = item.get("main", {}) or {}
        weather_arr = item.get("weather", []) or []
        w = weather_arr[0] if weather_arr else {}

        rain = item.get("rain") or {}
        snow = item.get("snow") or {}

        rows.append({
            # keep existing fields
            "dt_utc": dt_utc.isoformat().replace("+00:00", "Z"),
            "temp": main.get("temp"),
            "feels_like": main.get("feels_like"),
            "humidity": main.get("humidity"),
            "pressure": main.get("pressure"),
            "weather_main": w.get("main"),
            "weather_description": w.get("description"),

            # added useful fields (non-breaking)
            "dt_local": dt_local.isoformat(),
            "pop": item.get("pop"),                 # 0..1 precipitation probability
            "rain_3h_mm": rain.get("3h"),           # mm in last 3 hours (if provided)
            "snow_3h_mm": snow.get("3h"),           # mm in last 3 hours (if provided)
        })

    if not rows:
        return {
            "note": (
                "No 3-hour slots matched the requested LOCAL date/time_of_day. "
                "This can happen if the date is beyond API range (>~5 days), "
                "or the city/country query is invalid."
            ),
            "slots": [],
        }

    temps = [r["temp"] for r in rows if r.get("temp") is not None]
    return {
        "slots": rows,
        "temp_min": min(temps) if temps else None,
        "temp_max": max(temps) if temps else None,
        "temp_avg": (sum(temps) / len(temps)) if temps else None,
    }
