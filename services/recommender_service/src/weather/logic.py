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
        local_day = date.fromisoformat(_slot_local_date(s["dt_utc"]))  # ✅ local day
        if start <= local_day <= end:
            filtered.append(s)
    return filtered

def _build_model_daily(location_id: str, start: date, end: date) -> tuple[list[dict], list[str], dict]:
    """
    Returns:
      model_daily: list[dict] in your daily schema
      covered_dates: list[str] dates that models could fill
      meta: debug notes
    """
    meta: dict = {"temperature": None, "rainfall": None}
    model_daily: list[dict] = []

    temp_fc = load_sarima_temp_forecast(location_id, start, end)
    rain_fc = load_rain_risk_climatology(location_id, start, end)

    # loaders might return {"daily":[...]} or {"note": "..."} etc.
    temp_daily = temp_fc.get("daily") if isinstance(temp_fc, dict) else None
    rain_daily = rain_fc.get("daily") if isinstance(rain_fc, dict) else None

    if not isinstance(temp_daily, list):
        meta["temperature"] = temp_fc  # keep whatever note/error
        temp_daily = []

    if not isinstance(rain_daily, list):
        meta["rainfall"] = rain_fc
        rain_daily = []

    rain_by_date = {d.get("date"): d for d in rain_daily if isinstance(d, dict) and d.get("date")}

    for t in temp_daily:
        if not isinstance(t, dict) or not t.get("date"):
            continue
        day = t["date"]
        if not (start.isoformat() <= day <= end.isoformat()):
            continue

        r = rain_by_date.get(day, {})
        model_daily.append({
            "date": day,
            "temp_min": t.get("temp_min"),
            "temp_max": t.get("temp_max"),
            "temp_avg": t.get("temp_avg") or t.get("temp_c"),  # support either key
            "humidity_avg": None,
            "condition": r.get("condition") or "Unknown",
            "rain_risk": r.get("rain_risk") or r.get("risk"),
        })

    covered = [d["date"] for d in model_daily]
    return model_daily, covered, meta




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
            # ensure response has daily + filtered slots for the exact requested range
            api_fc["slots"] = slots_in_range
            api_fc["daily"] = api_daily

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

        # ✅ SAFE: loaders might return {"note": "..."} or something without "daily"
        temp_daily = temp_fc.get("daily") if isinstance(temp_fc, dict) else None
        rain_daily_list = rain_risk.get("daily") if isinstance(rain_risk, dict) else None

        if not isinstance(temp_daily, list):
            temp_daily = []

        if not isinstance(rain_daily_list, list):
            rain_daily_list = []

        rain_daily = {
            d["date"]: d
            for d in rain_daily_list
            if isinstance(d, dict) and d.get("date")
        }

        model_daily = []
        for t in temp_daily:
            if not isinstance(t, dict) or not t.get("date"):
                continue

            day = t["date"]
            if day in missing_dates:  # missing_dates already subset of requested
                rd = rain_daily.get(day, {})
                model_daily.append({
                    "date": day,
                    "temp_min": t.get("temp_min"),
                    "temp_max": t.get("temp_max"),
                    "temp_avg": t.get("temp_avg") or t.get("temp_c"),
                    "humidity_avg": None,
                    "condition": rd.get("condition") or "Unknown",
                    "rain_risk": rd.get("rain_risk") or rd.get("risk"),
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
                "daily": merged_daily,
                "slots": slots_in_range,
                "note": "Days missing from OpenWeather were filled using long-range models/climatology (if available).",
                "missing_dates_requested": missing_dates,
                "api_dates_present": sorted(list(api_dates)),
                "model_dates_filled": [d["date"] for d in model_daily],
                "model_debug": {
                    "temperature_loader": temp_fc if isinstance(temp_fc, dict) and "note" in temp_fc else None,
                    "rain_loader": rain_risk if isinstance(rain_risk, dict) and "note" in rain_risk else None,
                },
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
