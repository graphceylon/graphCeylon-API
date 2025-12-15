from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, Optional, List, Tuple

import pandas as pd
from collections import defaultdict
from datetime import date
from statistics import mean


from configs.recommender_service.config import WEATHER_RAW_DIR, DATA_CLEAN_DIR
from src.weather.openweather import fetch_openweather_for_city_and_day
from src.weather.models import load_sarima_temp_forecast, load_rain_risk_climatology
from zoneinfo import ZoneInfo
from datetime import datetime
from datetime import timedelta

def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

def _daily_dates_present(api_daily: list[dict]) -> set[str]:
    return {d["date"] for d in (api_daily or [])}

def _merge_daily(api_daily: list[dict], model_daily: list[dict]) -> list[dict]:
    """
    Prefer API daily for dates it has. For missing dates, use model/climatology daily.
    Returns a sorted list by date.
    """
    merged: dict[str, dict] = {}

    for d in (model_daily or []):
        merged[d["date"]] = {**d, "source": "long_range_models"}  # baseline

    for d in (api_daily or []):
        merged[d["date"]] = {**d, "source": "openweather_5day"}   # overwrite preferred

    return [merged[k] for k in sorted(merged.keys())]

COLOMBO = ZoneInfo("Asia/Colombo")

def _slot_local_date(dt_utc_str: str) -> str:
    # "2025-12-15T21:00:00Z"
    dt_utc = datetime.fromisoformat(dt_utc_str.replace("Z", "+00:00"))
    dt_local = dt_utc.astimezone(COLOMBO)
    return dt_local.date().isoformat()

def filter_slots_by_date_range(slots: list[dict], start_date: str, end_date: str) -> list[dict]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    filtered = []
    for s in slots:
        d = date.fromisoformat(s["dt_utc"][:10])
        if start <= d <= end:
            filtered.append(s)
    return filtered


def build_daily_forecast_from_slots(slots: list[dict]) -> list[dict]:
    by_day = defaultdict(list)

    for s in slots:
        day = _slot_local_date(s["dt_utc"])  # ✅ local day
        by_day[day].append(s)

    daily = []
    for day in sorted(by_day.keys()):
        day_slots = by_day[day]

        temps = [x["temp"] for x in day_slots if x.get("temp") is not None]
        hums  = [x["humidity"] for x in day_slots if x.get("humidity") is not None]

        mains = [x.get("weather_main") for x in day_slots if x.get("weather_main")]
        if "Rain" in mains:
            condition = "Rain"
        elif mains:
            condition = max(set(mains), key=mains.count)
        else:
            condition = "Unknown"

        daily.append({
            "date": day,
            "temp_min": min(temps) if temps else None,
            "temp_max": max(temps) if temps else None,
            "temp_avg": round(mean(temps), 2) if temps else None,
            "humidity_avg": round(mean(hums), 2) if hums else None,
            "condition": condition,
        })

    return daily


def _parse_ymd(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _days_ahead(target: date) -> int:
    return (target - date.today()).days


def forecast_weather_logic(payload: Dict[str, Any]) -> Dict[str, Any]:
    city = (payload.get("city") or "").strip()
    country = (payload.get("country") or "").strip()
    start_date = _parse_ymd(payload.get("start_date"))
    end_date = _parse_ymd(payload.get("end_date")) or start_date
    tod = payload.get("time_of_day")

    if not city:
        raise ValueError("city is required")
    if not start_date:
        raise ValueError("start_date is required")
    if not end_date:
        end_date = start_date

    # normalize location_id
    location_id = (
        city.lower().strip()
            .replace("’", "'")
            .replace("'", "")
            .replace("-", "_")
            .replace(" ", "_")
    )

    ahead = _days_ahead(start_date)

    # --- SHORT RANGE: try OpenWeather first ---
    if 0 <= ahead <= 5:
        api_fc = fetch_openweather_for_city_and_day(city, country, start_date, tod)

        # ✅ Always derive a daily summary for the requested date range from slots
        slots = api_fc.get("slots", [])
        slots_in_range = filter_slots_by_date_range(slots, str(start_date), str(end_date))
        api_daily = api_fc.get("daily") or build_daily_forecast_from_slots(slots_in_range)

        api_dates = {d["date"] for d in api_daily}  # dates OpenWeather actually covered
        requested_dates = {d.isoformat() for d in _daterange(start_date, end_date)}
        missing_dates = sorted(list(requested_dates - api_dates))


        # If ALL dates are present -> return pure API
        if not missing_dates:
            return {
                "source": "openweather_5day",
                "location_id": location_id,
                "city": city,
                "country": country,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "time_of_day": tod,
                "api_forecast": api_fc,
            }

        # Otherwise: fill missing dates using models/climatology
        # We’ll compute model forecasts ONLY for the missing range for efficiency
        miss_start = date.fromisoformat(missing_dates[0])
        miss_end = date.fromisoformat(missing_dates[-1])

        temp_fc = load_sarima_temp_forecast(location_id, miss_start, miss_end)
        rain_risk = load_rain_risk_climatology(location_id, miss_start, miss_end)

        # Convert model outputs into a "daily" list matching your API daily shape
        # (you can adjust keys based on your CSV schema)
        model_daily = []
        # If your loaders already return daily lists, just use them.
        # Otherwise, build them here from the returned data structures.
        # Example assumes they return dicts keyed by date:
        # temp_fc["daily"] = [{"date": "...", "temp_avg": ... , ...}]
        # rain_risk["daily"] = [{"date": "...", "rain_risk": ...}]
        temp_daily = temp_fc.get("daily", [])
        rain_daily = {d["date"]: d for d in rain_risk.get("daily", [])}

        for t in temp_daily:
            day = t["date"]
            if day in requested_dates and day in missing_dates:
                rd = rain_daily.get(day, {})
                model_daily.append({
                    "date": day,
                    "temp_min": t.get("temp_min"),
                    "temp_max": t.get("temp_max"),
                    "temp_avg": t.get("temp_avg"),
                    "humidity_avg": None,
                    "condition": rd.get("condition") or "Unknown",
                    "rain_risk": rd.get("rain_risk"),
                })

        merged_daily = _merge_daily(api_daily, model_daily)

        return {
            "source": "hybrid_openweather_plus_models",
            "location_id": location_id,
            "city": city,
            "country": country,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "time_of_day": tod,
            "api_forecast": {
                "daily": merged_daily,               # ✅ will now include 15,16 (from api)
                "slots": slots_in_range,             # ✅ filtered slots only
                "note": "Days missing from OpenWeather were filled using long-range models/climatology.",
                "missing_dates_filled": missing_dates,   # ✅ now should be only ['2025-12-17']
                "api_dates_present": sorted(list(api_dates)),
    },
        }

    # --- LONG RANGE ONLY ---
    temp_fc = load_sarima_temp_forecast(location_id, start_date, end_date)
    rain_risk = load_rain_risk_climatology(location_id, start_date, end_date)

    return {
        "source": "long_range_models",
        "location_id": location_id,
        "city": city,
        "country": country,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "time_of_day": tod,
        "temperature": temp_fc,
        "rainfall_risk": rain_risk,
    }
