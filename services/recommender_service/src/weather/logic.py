from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Dict, Optional, List
from collections import defaultdict
from statistics import mean
from zoneinfo import ZoneInfo
from pathlib import Path

from src.weather.openweather import fetch_openweather_for_city_and_day
from src.weather.models import build_monthly_weather

COLOMBO = ZoneInfo("Asia/Colombo")


def _parse_ymd(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _days_ahead_local(target: date) -> int:
    """Days ahead computed using Sri Lanka local date (not server UTC)."""
    today_local = datetime.now(COLOMBO).date()
    return (target - today_local).days


def _normalize_location_id(city: str) -> str:
    return (
        city.lower().strip()
        .replace("’", "'")
        .replace("'", "")
        .replace("-", "_")
        .replace(" ", "_")
    )


def _slot_local_date(dt_utc_str: str) -> str:
    dt_utc = datetime.fromisoformat(dt_utc_str.replace("Z", "+00:00"))
    dt_local = dt_utc.astimezone(COLOMBO)
    return dt_local.date().isoformat()


def build_daily_forecast_from_slots(slots: List[dict]) -> List[dict]:
    """
    Build daily summaries from 3-hourly slots, grouped by LOCAL date.
    Also computes:
      - mean_mm: sum of rain_3h_mm across that day (if present)
      - rain_risk: from average pop (if present)
    INTERNAL daily schema:
      - date,temp_min,temp_max,temp_avg,humidity_avg,condition,rain_risk,mean_mm
    """
    by_day = defaultdict(list)
    for s in slots or []:
        if not isinstance(s, dict) or "dt_utc" not in s:
            continue
        day = _slot_local_date(s["dt_utc"])
        by_day[day].append(s)

    daily: List[dict] = []
    for day in sorted(by_day.keys()):
        day_slots = by_day[day]

        temps = [x.get("temp") for x in day_slots if x.get("temp") is not None]
        hums = [x.get("humidity") for x in day_slots if x.get("humidity") is not None]

        mains = [x.get("weather_main") for x in day_slots if x.get("weather_main")]
        if "Rain" in mains:
            condition = "Rain"
        elif mains:
            condition = max(set(mains), key=mains.count)
        else:
            condition = "Unknown"

        rain_vals = [x.get("rain_3h_mm") for x in day_slots if x.get("rain_3h_mm") is not None]
        mean_mm = round(sum(rain_vals), 2) if rain_vals else None

        pops = [x.get("pop") for x in day_slots if x.get("pop") is not None]
        pop_avg = (sum(pops) / len(pops)) if pops else None

        rain_risk = None
        if pop_avg is not None:
            if pop_avg >= 0.7:
                rain_risk = "High"
            elif pop_avg <= 0.3:
                rain_risk = "Low"
            else:
                rain_risk = "Medium"

        daily.append(
            {
                "date": day,
                "temp_min": min(temps) if temps else None,
                "temp_max": max(temps) if temps else None,
                "temp_avg": round(mean(temps), 2) if temps else None,
                "humidity_avg": round(mean(hums), 2) if hums else None,
                "condition": condition,
                "rain_risk": rain_risk,
                "mean_mm": mean_mm,
            }
        )

    return daily


def _to_public_daily_schema(daily_internal: List[dict]) -> List[dict]:
    """Convert internal daily rows -> your public schema (ds/temp_c/min_c/max_c...)."""
    out: List[dict] = []
    for d in daily_internal or []:
        if not isinstance(d, dict):
            continue
        out.append(
            {
                "ds": d.get("date"),
                "temp_c": d.get("temp_avg"),
                "min_c": d.get("temp_min"),
                "max_c": d.get("temp_max"),
                "condition": d.get("condition") or "Unknown",
                "rain_risk": d.get("rain_risk"),
                "mean_mm": d.get("mean_mm"),
            }
        )
    return out


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

    location_id = _normalize_location_id(city)

    ahead_start = _days_ahead_local(start_date)
    ahead_end = _days_ahead_local(end_date)

    # ✅ CRITICAL RULE (your requirement):
    # Only use OpenWeather if *entire* requested range is within 0..5 days.
    can_try_openweather = (0 <= ahead_start <= 5) and (0 <= ahead_end <= 5)

    debug = {
        "today_local": datetime.now(COLOMBO).date().isoformat(),
        "ahead_start": ahead_start,
        "ahead_end": ahead_end,
        "can_try_openweather": can_try_openweather,
        "location_id": location_id,
        "logic_file": str(Path(__file__).resolve()),
    }

    # ✅ OUTSIDE API WINDOW -> MONTHLY ONLY (temp + rainfall merged)
    if not can_try_openweather:
        monthly_pack = build_monthly_weather(location_id, start_date, end_date)
        return {
            "city": city,
            "country": country,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "time_of_day": tod,
            "source": "long_range_models_monthly",
            "forecast_summary": "Long-range monthly forecast from SARIMA + climatology.",
            "daily": [],
            "monthly": monthly_pack.get("monthly", []),
            "warnings": [],
            "debug": {
                **debug,
                "temperature": monthly_pack.get("temperature_monthly"),
                "rainfall": monthly_pack.get("rainfall_monthly"),
            },
        }

    # ✅ WITHIN API WINDOW -> DAILY API FOR EACH DAY IN RANGE
    all_slots: List[dict] = []
    warnings: List[str] = []

    d = start_date
    while d <= end_date:
        try:
            api_fc = fetch_openweather_for_city_and_day(city, country, d, tod)
        except Exception as e:
            warnings.append(f"openweather_error_{d.isoformat()}: {type(e).__name__}: {e}")
            d += timedelta(days=1)
            continue

        day_slots = api_fc.get("slots", []) if isinstance(api_fc, dict) else []
        if not day_slots:
            note = api_fc.get("note") if isinstance(api_fc, dict) else None
            warnings.append(f"openweather_no_slots_{d.isoformat()}: {note or 'no slots'}")
        else:
            all_slots.extend(day_slots)

        d += timedelta(days=1)

    # If API returned nothing across the whole range -> fall back to MONTHLY ONLY
    if not all_slots:
        monthly_pack = build_monthly_weather(location_id, start_date, end_date)
        return {
            "city": city,
            "country": country,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "time_of_day": tod,
            "source": "long_range_models_monthly",
            "forecast_summary": "No OpenWeather slots matched; used long-range models.",
            "daily": [],
            "monthly": monthly_pack.get("monthly", []),
            "warnings": warnings,
            "debug": {
                **debug,
                "temperature": monthly_pack.get("temperature_monthly"),
                "rainfall": monthly_pack.get("rainfall_monthly"),
            },
        }

    daily_internal = build_daily_forecast_from_slots(all_slots)
    daily_public = _to_public_daily_schema(daily_internal)

    return {
        "city": city,
        "country": country,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "time_of_day": tod,
        "source": "short_range_api_daily",
        "forecast_summary": "Short-range daily forecast from API",
        "daily": daily_public,
        "monthly": [],
        "warnings": warnings,
        "debug": debug,
    }
