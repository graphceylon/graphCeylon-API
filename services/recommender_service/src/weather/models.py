from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional, List

import pandas as pd

from configs.recommender_service.config import DATA_CLEAN_DIR


def _date_range(start: date, end: Optional[date]) -> List[date]:
    if end is None:
        return [start]
    if end < start:
        return [start]
    cur = start
    out = []
    while cur <= end:
        out.append(cur)
        cur = cur.replace(day=1)  # keep month-aligned if caller passes month dates
        # move to next month safely
        y = cur.year + (cur.month // 12)
        m = (cur.month % 12) + 1
        cur = cur.replace(year=y, month=m, day=1)
    return out


def load_sarima_temp_forecast(location_id: str, start: date, end: Optional[date]) -> Dict[str, Any]:
    """
    Expect you have a CSV in clean/ with monthly temperature forecasts.
    If your file name differs, change it here.
    """
    path = DATA_CLEAN_DIR / "sarima_temperature_forecast.csv"  # <-- adjust if your filename differs
    if not path.exists():
        return {"note": f"Temperature forecast file not found: {path}"}

    df = pd.read_csv(path)
    df["ds"] = pd.to_datetime(df["ds"]).dt.date

    loc = df[df["location_id"] == location_id].copy()
    if loc.empty:
        return {"note": f"No temperature forecast found for location_id={location_id}"}

    mask = (loc["ds"] >= start) & (loc["ds"] <= (end or start))
    rows = loc.loc[mask, ["ds", "pred_temp"]].to_dict(orient="records")

    return {"unit": "celsius", "values": rows}


def load_rain_risk_climatology(location_id: str, start: date, end: Optional[date]) -> Dict[str, Any]:
    """
    Expect a climatology file like: clean/rainfall_climatology_risk.csv
    containing per-location per-month percentiles + risk labels.
    """
    path = DATA_CLEAN_DIR / "rainfall_climatology.csv"  # <-- adjust to your saved climatology output
    if not path.exists():
        return {"note": f"Rainfall climatology file not found: {path}"}

    df = pd.read_csv(path)
    # required columns expected: location_id, month, risk_level, p25, p75, p90, mean_mm (etc)
    df["location_id"] = df["location_id"].astype(str)

    loc = df[df["location_id"] == location_id].copy()
    if loc.empty:
        return {"note": f"No rainfall climatology found for location_id={location_id}"}

    months = []
    cur = start.replace(day=1)
    end_m = (end or start).replace(day=1)
    while cur <= end_m:
        months.append(cur.month)
        y = cur.year + (cur.month // 12)
        m = (cur.month % 12) + 1
        cur = cur.replace(year=y, month=m, day=1)

    out = []
    for m in months:
        row = loc[loc["month"] == m]
        if row.empty:
            continue
        r = row.iloc[0].to_dict()
        out.append({
            "month": int(m),
            "risk_level": r.get("risk_level"),
            "mean_mm": r.get("mean_mm"),
            "p25": r.get("p25"),
            "p75": r.get("p75"),
            "p90": r.get("p90"),
        })

    return {"method": "percentile_climatology", "values": out}
