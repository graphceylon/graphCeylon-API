from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, Optional, Literal, List

import requests

from configs.recommender_service.config import OPENWEATHER_API_KEY


TimeOfDay = Optional[Literal["morning", "afternoon", "evening"]]


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
    if not OPENWEATHER_API_KEY:
        raise RuntimeError("OPENWEATHER_API_KEY not set")

    # Using city-based query here (simpler). If you prefer lat/lon from KG, we can switch.
    q = f"{city},{country}" if country else city

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": q, "appid": OPENWEATHER_API_KEY, "units": "metric"}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    hours = _tod_hours(time_of_day)

    rows = []
    for item in data.get("list", []):
        dt = datetime.utcfromtimestamp(item["dt"])
        if dt.date() != target_date:
            continue
        if dt.hour not in hours:
            continue

        main = item.get("main", {})
        weather_arr = item.get("weather", [])
        w = weather_arr[0] if weather_arr else {}

        rows.append({
            "dt_utc": dt.isoformat() + "Z",
            "temp": main.get("temp"),
            "feels_like": main.get("feels_like"),
            "humidity": main.get("humidity"),
            "pressure": main.get("pressure"),
            "weather_main": w.get("main"),
            "weather_description": w.get("description"),
        })

    if not rows:
        return {
            "note": "No 3-hour slots matched the requested date/time_of_day (date might be >5 days ahead).",
            "slots": [],
        }

    # summary stats
    temps = [r["temp"] for r in rows if r["temp"] is not None]
    return {
        "slots": rows,
        "temp_min": min(temps) if temps else None,
        "temp_max": max(temps) if temps else None,
        "temp_avg": (sum(temps) / len(temps)) if temps else None,
    }
