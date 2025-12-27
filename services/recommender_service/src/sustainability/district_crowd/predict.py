from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union

import pandas as pd


from pathlib import Path
from services.recommender_service.src.forecast.arrivals_sarima import forecast_month_arrivals

ROOT_DATA_ROOT = Path("data/recommender_service")
SERVICE_DATA_ROOT = Path("services/recommender_service/data/recommender_service")

ATTRACTIONS_JSON = SERVICE_DATA_ROOT / "clean/kg/attractions_clean.json"
SLTDA_ARRIVALS_MONTHLY = ROOT_DATA_ROOT / "clean/sltda_arrivals_monthly.csv"

BLENDED_SHARE_JSON = ROOT_DATA_ROOT / "clean/sustainability/district_share_blended.json"
DISTRICT_THRESHOLDS_JSON = ROOT_DATA_ROOT / "clean/sustainability/district_thresholds_2018_2019.json"
GLOBAL_THRESHOLDS_JSON = ROOT_DATA_ROOT / "clean/sustainability/global_thresholds_2018_2019.json"

DateLike = Union[str, datetime, date, pd.Timestamp]


def to_month_start(dt: DateLike) -> pd.Timestamp:
    t = pd.to_datetime(dt)
    return pd.Timestamp(year=int(t.year), month=int(t.month), day=1)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_arrivals_df() -> pd.DataFrame:
    df = pd.read_csv(SLTDA_ARRIVALS_MONTHLY)
    cols = {c.lower(): c for c in df.columns}
    date_col = cols.get("date") or cols.get("ds") or list(df.columns)[0]
    arr_col = cols.get("arrivals") or cols.get("total_arrivals") or cols.get("foreign_arrivals")
    if not arr_col:
        for low, orig in cols.items():
            if "arrival" in low:
                arr_col = orig
                break
    if not arr_col:
        raise ValueError(f"Could not detect arrivals column in {SLTDA_ARRIVALS_MONTHLY}")

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.rename(columns={date_col: "date", arr_col: "arrivals"})
    df["month_start"] = df["date"].dt.to_period("M").dt.to_timestamp()
    return df[["month_start", "arrivals"]].copy()

def _canonicalize_district_name(user_district: str, shares: Dict[str, Any]) -> str:
    """
    Map user-provided district to the canonical key used in share JSONs.
    Handles case differences and minor formatting differences.
    """
    u = str(user_district).strip().lower()
    for k in shares.keys():
        if str(k).strip().lower() == u:
            return k
    return user_district  # fallback as-is



def get_total_arrivals_for_month(month_start: pd.Timestamp) -> Optional[float]:
    df = _load_arrivals_df()
    row = df[df["month_start"] == month_start]
    if row.empty:
        return None
    return float(row.iloc[0]["arrivals"])


def crowd_level_from_thresholds(value: float, thresholds: Dict[str, float]) -> str:
    """
    Minimal 4-level crowd mapping using percentiles:
      <= p25 -> Low
      <= p50 -> Moderate
      <= p75 -> High
      >  p75 -> VeryHigh

    You can tighten to p90 if you want "Extreme".
    """
    p25 = thresholds.get("p25")
    p50 = thresholds.get("p50")
    p75 = thresholds.get("p75")

    if p25 is None or p50 is None or p75 is None:
        return "Unknown"

    if value <= p25:
        return "Low"
    if value <= p50:
        return "Moderate"
    if value <= p75:
        return "High"
    return "VeryHigh"


def predict_district_crowd(district: str, dt: DateLike) -> Dict[str, Any]:
    month_start = to_month_start(dt)

    shares = _load_json(BLENDED_SHARE_JSON)
    district = _canonicalize_district_name(district, shares)
    district_thresholds = _load_json(DISTRICT_THRESHOLDS_JSON)
    global_thresholds = _load_json(GLOBAL_THRESHOLDS_JSON)

    share = float(shares.get(district, 0.0))
    total_arrivals = get_total_arrivals_for_month(month_start)

    if total_arrivals is None:
        try:
            total_arrivals = float(forecast_month_arrivals(month_start))
            arrivals_source = "sarima_forecast"
        except Exception:
            return {
                "status": "no_data",
                "district": district,
                "month_start": str(month_start.date()),
                "reason": "Month not found in sltda_arrivals_monthly.csv and SARIMA forecast unavailable.",
            }
    else:
        arrivals_source = "sltda_csv"


    expected = float(total_arrivals) * share
    th = district_thresholds.get(district) or global_thresholds
    level = crowd_level_from_thresholds(expected, th if isinstance(th, dict) else {})

    return {
        "status": "ok",
        "district": district,
        "month_start": str(month_start.date()),
        "arrivals_source": arrivals_source,
        "total_arrivals_month": float(total_arrivals),
        "district_share_blended": share,
        "expected_district_visitors": expected,
        "crowd_level": level,
        "thresholds_used": "district" if district in district_thresholds else "global",
        "thresholds": th,
    }


def _iter_attractions(obj):
    if isinstance(obj, dict) and "attractions" in obj and isinstance(obj["attractions"], list):
        for x in obj["attractions"]:
            if isinstance(x, dict):
                yield x
        return

    if isinstance(obj, list):
        for x in obj:
            if isinstance(x, dict):
                yield x
        return

    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, dict):
                yield v



def _load_attraction_index() -> Dict[str, Dict[str, Any]]:
    obj = json.loads(ATTRACTIONS_JSON.read_text(encoding="utf-8"))
    idx: Dict[str, Dict[str, Any]] = {}
    for r in _iter_attractions(obj):
        aid = r.get("attraction_id") or r.get("poi_id") or r.get("id")
        if aid:
            idx[str(aid)] = r
    return idx



def predict_attraction_crowd(attraction_id: str, dt: DateLike) -> Dict[str, Any]:
    idx = _load_attraction_index()
    a = idx.get(attraction_id)
    if not a:
        return {"status": "not_found", "attraction_id": attraction_id}

    district = a.get("district")
    title = a.get("title") or a.get("name")

    if not district:
        return {
            "status": "no_district",
            "attraction_id": attraction_id,
            "title": title,
        }

    out = predict_district_crowd(district, dt)
    out["attraction_id"] = attraction_id
    out["attraction_title"] = title
    return out
