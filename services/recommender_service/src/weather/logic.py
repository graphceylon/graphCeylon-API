from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Dict, Optional, List, Tuple


from collections import defaultdict
from statistics import mean
from zoneinfo import ZoneInfo

from src.weather.openweather import fetch_openweather_for_city_and_day
from src.weather.models import load_sarima_temp_forecast, load_rain_risk_climatology,build_monthly_weather


COLOMBO = ZoneInfo("Asia/Colombo")


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _merge_daily(api_daily: list[dict], model_daily: list[dict]) -> list[dict]:
    """
    Prefer API daily for dates it has. For missing dates, use model/climatology daily.
    Returns a sorted list by date.
    """
    merged: dict[str, dict] = {}

    for d in (model_daily or []):
        if isinstance(d, dict) and d.get("date"):
            merged[d["date"]] = {**d, "source": "long_range_models"}

    for d in (api_daily or []):
        if isinstance(d, dict) and d.get("date"):
            merged[d["date"]] = {**d, "source": "openweather_5day"}

    return [merged[k] for k in sorted(merged.keys())]


def _slot_local_date(dt_utc_str: str) -> str:
    # accepts "2025-12-15T21:00:00Z" or "2025-12-15T21:00:00+00:00"
    dt_utc = datetime.fromisoformat(dt_utc_str.replace("Z", "+00:00"))
    dt_local = dt_utc.astimezone(COLOMBO)
    return dt_local.date().isoformat()


def filter_slots_by_date_range(slots: list[dict], start_date: str, end_date: str) -> list[dict]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    filtered = []
    for s in slots or []:
        if not isinstance(s, dict) or "dt_utc" not in s:
            continue
        local_day = date.fromisoformat(_slot_local_date(s["dt_utc"]))
        if start <= local_day <= end:
            filtered.append(s)
    return filtered


def build_daily_forecast_from_slots(slots: list[dict]) -> list[dict]:
    """
    Build daily summaries from 3-hourly slots, grouped by LOCAL (Asia/Colombo) date.
    """
    by_day = defaultdict(list)

    for s in slots or []:
        if not isinstance(s, dict) or "dt_utc" not in s:
            continue
        day = _slot_local_date(s["dt_utc"])
        by_day[day].append(s)

    daily = []
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


def _normalize_location_id(city: str) -> str:
    return (
        city.lower().strip()
            .replace("’", "'")
            .replace("'", "")
            .replace("-", "_")
            .replace(" ", "_")
    )


def _build_model_daily(location_id: str, start: date, end: date) -> Tuple[List[dict], List[str], dict]:
    """
    Combine temperature daily + rainfall daily (by date) into a single daily list.
    Returns: model_daily, covered_dates, meta
    """
    meta: dict = {"temperature": None, "rainfall": None}

    temp_fc = load_sarima_temp_forecast(location_id, start, end)
    rain_fc = load_rain_risk_climatology(location_id, start, end)

    temp_daily = temp_fc.get("daily") if isinstance(temp_fc, dict) else None
    rain_daily = rain_fc.get("daily") if isinstance(rain_fc, dict) else None

    if not isinstance(temp_daily, list):
        meta["temperature"] = temp_fc
        temp_daily = []
    if not isinstance(rain_daily, list):
        meta["rainfall"] = rain_fc
        rain_daily = []

    rain_by_date = {
        d.get("date"): d for d in rain_daily
        if isinstance(d, dict) and d.get("date")
    }

    model_daily: List[dict] = []
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
            "temp_avg": t.get("temp_avg") or t.get("temp_c"),
            "humidity_avg": t.get("humidity_avg"),
            "condition": r.get("condition") or t.get("condition") or "Unknown",
            "rain_risk": r.get("rain_risk") or r.get("risk"),
        })

    covered = [d["date"] for d in model_daily]
    return model_daily, covered, meta


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _month_range(start: date, end: date) -> List[date]:
    """Return list of month-start dates from start..end inclusive."""
    cur = start.replace(day=1)
    end_m = end.replace(day=1)
    out = []
    while cur <= end_m:
        out.append(cur)
        # next month
        y = cur.year + (cur.month // 12)
        m = (cur.month % 12) + 1
        cur = cur.replace(year=y, month=m, day=1)
    return out


def _daily_to_monthly(daily: List[dict], start: date, end: date) -> List[dict]:
    """
    Compress daily model output into monthly records:
      - 1 record if within 1 month
      - N records if spans N months
    Chooses temp_avg as average of available daily temps for that month.
    Chooses rain_risk as the most common non-null label in the month.
    """
    by_month: Dict[str, List[dict]] = defaultdict(list)
    for row in daily or []:
        if not isinstance(row, dict) or not row.get("date"):
            continue
        yyyy_mm = row["date"][:7]  # "YYYY-MM"
        by_month[yyyy_mm].append(row)

    out = []
    for m_start in _month_range(start, end):
        yyyy_mm = _month_key(m_start)
        rows = by_month.get(yyyy_mm, [])

        temps = [r.get("temp_avg") for r in rows if r.get("temp_avg") is not None]
        temp_val = round(mean(temps), 2) if temps else None

        risks = [r.get("rain_risk") for r in rows if r.get("rain_risk")]
        risk_val = max(set(risks), key=risks.count) if risks else None

        conds = [r.get("condition") for r in rows if r.get("condition")]
        cond_val = max(set(conds), key=conds.count) if conds else "Unknown"

        out.append({
            "month": yyyy_mm,
            "temp_avg": temp_val,
            "rain_risk": risk_val,
            "condition": cond_val,
        })

    return out


def _within_one_month(start: date, end: date) -> bool:
    return start.year == end.year and start.month == end.month


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

    # We only attempt OpenWeather if the *requested range* starts within next 5 days
    # AND end_date also not too far (otherwise it cannot fully cover it).
    ahead_start = _days_ahead(start_date)
    ahead_end = _days_ahead(end_date)

    can_try_openweather = (0 <= ahead_start <= 5) and (0 <= ahead_end <= 5)

    if can_try_openweather:
        try:
            api_fc = fetch_openweather_for_city_and_day(city, country, start_date, tod)
        except Exception:
            # API failed -> monthly fallback
            monthly_pack = build_monthly_weather(location_id, start_date, end_date)
            return {
                "source": "long_range_models_monthly",
                "location_id": location_id,
                "city": city,
                "country": country,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "time_of_day": tod,
                "monthly": monthly_pack["monthly"],
                "debug": {
                    "temperature": monthly_pack["temperature_monthly"],
                    "rainfall": monthly_pack["rainfall_monthly"],
                },
            }

        slots = api_fc.get("slots", []) if isinstance(api_fc, dict) else []
        if not slots:
            # No slots matched (date may still be within 0..5 but no slots for TOD) -> monthly fallback
            monthly_pack = build_monthly_weather(location_id, start_date, end_date)
            return {
                "source": "long_range_models_monthly",
                "location_id": location_id,
                "city": city,
                "country": country,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "time_of_day": tod,
                "monthly": monthly_pack["monthly"],
                "note": api_fc.get("note") if isinstance(api_fc, dict) else None,
            }

        # DAILY result (since we are within OpenWeather cover window)
        api_daily = build_daily_forecast_from_slots(slots)

        return {
            "source": "openweather_5day_daily",
            "location_id": location_id,
            "city": city,
            "country": country,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "time_of_day": tod,
            "daily": api_daily,
            "slots": slots,
        }

    # ---- Outside OpenWeather coverage -> MONTHLY ONLY (1 record per month spanned) ----
    monthly_pack = build_monthly_weather(location_id, start_date, end_date)

    return {
        "source": "long_range_models_monthly",
        "location_id": location_id,
        "city": city,
        "country": country,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "time_of_day": tod,
        "monthly": monthly_pack["monthly"],  # ✅ 1 per month (Jan, Feb, Mar, Apr = 4)
        # optional debug if you want
        "debug": {
            "temperature": monthly_pack["temperature_monthly"],
            "rainfall": monthly_pack["rainfall_monthly"],
        },
    }