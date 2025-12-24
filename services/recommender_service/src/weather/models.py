from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, List, Tuple
from collections import defaultdict
from statistics import mean

import pandas as pd
from datetime import timedelta

from configs.recommender_service.config import DATA_CLEAN_DIR


def _pick_col(cols: List[str], candidates: List[str]) -> Optional[str]:
    cols_lower = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    return None


def _month_key_from_date(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _iter_months(start: date, end: date) -> List[date]:
    cur = start.replace(day=1)
    end_m = end.replace(day=1)
    out = []
    while cur <= end_m:
        out.append(cur)
        y = cur.year + (cur.month // 12)
        m = (cur.month % 12) + 1
        cur = cur.replace(year=y, month=m, day=1)
    return out


def load_sarima_temp_monthly(location_id: str, start: date, end: Optional[date]) -> Dict[str, Any]:
    """
    Reads sarima_temperature_forecast.csv and returns exactly 1 record per month in range.
    Expected columns: location_id, date (YYYY-MM-01), temp_c
    """
    try:
        path = DATA_CLEAN_DIR / "sarima_temperature_forecast.csv"
        if not path.exists():
            return {"note": f"Temperature forecast file not found: {path}", "monthly": []}

        df = pd.read_csv(path)

        loc_col = _pick_col(df.columns.tolist(), ["location_id", "location", "loc_id", "loc"])
        date_col = _pick_col(df.columns.tolist(), ["date", "ds"])
        temp_col = _pick_col(
                df.columns.tolist(),
                [
                    "temp_c",
                    "temp_avg",
                    "pred_temp_c",      # ✅ your file uses this
                    "predicted_temp_c",
                    "pred_temp",
                    "yhat",
                    "yhat_mean",
                    "forecast_temp_c",
                ],
            )


        if not loc_col or not date_col or not temp_col:
            return {"note": f"Temperature CSV missing required columns. Found: {list(df.columns)}", "monthly": []}

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.date
        df = df.dropna(subset=[date_col])

        loc = df[df[loc_col].astype(str) == str(location_id)].copy()
        if loc.empty:
            return {"note": f"No temperature forecast found for location_id={location_id}", "monthly": []}

        end = end or start

        # map (year, month) -> temp
        month_map: Dict[Tuple[int, int], float] = {}
        for _, r in loc.iterrows():
            d = r[date_col]
            v = r[temp_col]
            if pd.isna(v):
                continue
            month_map[(d.year, d.month)] = float(v)

        monthly = []
        for m_start in _iter_months(start, end):
            v = month_map.get((m_start.year, m_start.month))
            monthly.append({
                "month": _month_key_from_date(m_start),
                "temp_avg": v,   # you can rename to temp_c if you want
            })

        return {"unit": "celsius", "monthly": monthly}

    except Exception as e:
        return {"note": f"SARIMA monthly temp loader failed: {type(e).__name__}: {e}", "monthly": []}


def load_rain_risk_monthly(location_id: str, start: date, end: Optional[date]) -> Dict[str, Any]:
    """
    Reads rainfall_climatology.csv and returns 1 record per month in range.
    Risk is computed per-location using q25/q75 of mean rainfall across the 12 months.
    """
    try:
        path = DATA_CLEAN_DIR / "rainfall_climatology.csv"
        if not path.exists():
            return {"note": f"Rainfall climatology file not found: {path}", "monthly": []}

        df = pd.read_csv(path)

        loc_col   = _pick_col(df.columns.tolist(), ["location_id", "location", "loc_id", "loc", "place_id"])
        month_col = _pick_col(df.columns.tolist(), ["month", "month_num"])
        mean_col  = _pick_col(df.columns.tolist(), ["mean_rainfall", "mean_mm", "mean", "avg_mm"])

        if not loc_col or not month_col or not mean_col:
            return {"note": f"Rainfall CSV missing required columns. Found: {list(df.columns)}", "monthly": []}

        df[loc_col] = df[loc_col].astype(str)
        loc = df[df[loc_col] == str(location_id)].copy()
        if loc.empty:
            return {"note": f"No rainfall climatology found for location_id={location_id}", "monthly": []}

        # thresholds across months for this location
        q25 = loc[mean_col].quantile(0.25)
        q75 = loc[mean_col].quantile(0.75)

        month_mean_map: Dict[int, float] = {}
        for _, r in loc.iterrows():
            m = int(r[month_col])
            month_mean_map[m] = float(r[mean_col])

        def risk_for_month(m: int) -> Optional[str]:
            mean_r = month_mean_map.get(m)
            if mean_r is None:
                return None
            if mean_r >= q75:
                return "High"
            if mean_r <= q25:
                return "Low"
            return "Medium"

        end = end or start

        monthly = []
        for m_start in _iter_months(start, end):
            m = m_start.month
            risk = risk_for_month(m)
            monthly.append({
                "month": _month_key_from_date(m_start),
                "rain_risk": risk,
                "condition": "Rain" if risk == "High" else "Unknown",
                "mean_mm": month_mean_map.get(m),
            })

        return {"method": "percentile_climatology", "monthly": monthly}

    except Exception as e:
        return {"note": f"Rainfall monthly loader failed: {type(e).__name__}: {e}", "monthly": []}


def build_monthly_weather(location_id: str, start: date, end: date) -> Dict[str, Any]:
    """
    Combine monthly temp + monthly rain into one aligned monthly array.
    """
    temp = load_sarima_temp_monthly(location_id, start, end)
    rain = load_rain_risk_monthly(location_id, start, end)

    t_rows = temp.get("monthly") if isinstance(temp, dict) else []
    r_rows = rain.get("monthly") if isinstance(rain, dict) else []

    r_by_month = {r["month"]: r for r in r_rows if isinstance(r, dict) and r.get("month")}

    monthly = []
    for t in t_rows:
        if not isinstance(t, dict) or not t.get("month"):
            continue
        m = t["month"]
        r = r_by_month.get(m, {})
        monthly.append({
            "month": m,
            "temp_avg": t.get("temp_avg"),
            "rain_risk": r.get("rain_risk"),
            "condition": r.get("condition") or "Unknown",
            "mean_mm": r.get("mean_mm"),
        })

    return {
        "monthly": monthly,
        "temperature_monthly": temp,
        "rainfall_monthly": rain,
    }
def load_sarima_temp_forecast(location_id: str, start: date, end: Optional[date]) -> Dict[str, Any]:
    """
    BACKWARD-COMPAT wrapper.
    Old code expects {"daily":[...]}.
    We'll generate daily by repeating the monthly value (same as your older behavior),
    but you will NOT use this path for long-range output anymore.
    """
    end = end or start
    monthly_pack = load_sarima_temp_monthly(location_id, start, end)
    monthly = monthly_pack.get("monthly", [])

    # map (YYYY-MM) -> value
    m_map = {m["month"]: m.get("temp_avg") for m in monthly if isinstance(m, dict) and m.get("month")}

    daily = []
    d = start
    while d <= end:
        key = f"{d.year:04d}-{d.month:02d}"
        v = m_map.get(key)
        daily.append({
            "date": d.isoformat(),
            "temp_min": v,
            "temp_max": v,
            "temp_avg": v,
            "humidity_avg": None,
            "condition": "Unknown",
            "rain_risk": None,
        })
        d += timedelta(days=1)

    return {"unit": "celsius", "daily": daily, "note": monthly_pack.get("note")}


def load_rain_risk_climatology(location_id: str, start: date, end: Optional[date]) -> Dict[str, Any]:
    """
    BACKWARD-COMPAT wrapper.
    Old code expects {"daily":[...]}.
    We'll generate daily by repeating the monthly risk label.
    """
    end = end or start
    monthly_pack = load_rain_risk_monthly(location_id, start, end)
    monthly = monthly_pack.get("monthly", [])

    m_map = {m["month"]: m for m in monthly if isinstance(m, dict) and m.get("month")}

    daily = []
    d = start
    while d <= end:
        key = f"{d.year:04d}-{d.month:02d}"
        info = m_map.get(key, {})
        daily.append({
            "date": d.isoformat(),
            "rain_risk": info.get("rain_risk"),
            "condition": info.get("condition") or "Unknown",
        })
        d += timedelta(days=1)

    return {"method": monthly_pack.get("method"), "daily": daily, "note": monthly_pack.get("note")}