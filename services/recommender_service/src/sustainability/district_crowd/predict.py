from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union

import pandas as pd


from pathlib import Path
from services.recommender_service.src.forecast.arrivals_sarima import forecast_month_arrivals

from pathlib import Path

from pathlib import Path

def _find_repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / "data").exists() and (parent / "services").exists() and (parent / "configs").exists():
            return parent
    return p.parents[5]  # fallback

REPO_ROOT = _find_repo_root()
ROOT_DATA_ROOT = REPO_ROOT / "data" / "recommender_service"


# ✅ attractions must come ONLY from this file
ATTRACTIONS_JSON = ROOT_DATA_ROOT / "clean/kg/attractions_clean.json"
if not ATTRACTIONS_JSON.exists():
    raise FileNotFoundError(f"[FATAL] attractions_clean.json not found at {ATTRACTIONS_JSON.resolve()}")

# ✅ arrivals monthly (used to lookup known months)
SLTDA_ARRIVALS_MONTHLY = ROOT_DATA_ROOT / "clean/sltda_arrivals_monthly.csv"
if not SLTDA_ARRIVALS_MONTHLY.exists():
    raise FileNotFoundError(f"[FATAL] sltda_arrivals_monthly.csv not found at {SLTDA_ARRIVALS_MONTHLY.resolve()}")

# ✅ district crowd artifacts produced by your builders
BLENDED_SHARE_JSON = ROOT_DATA_ROOT / "clean/sustainability/district_share_blended.json"

# ✅ IMPORTANT: use the *pressure* thresholds you built (domestic multipliers already included)
DISTRICT_THRESHOLDS_JSON = ROOT_DATA_ROOT / "clean/sustainability/district_thresholds_pressure_2018_2019.json"
GLOBAL_THRESHOLDS_JSON = ROOT_DATA_ROOT / "clean/sustainability/global_thresholds_pressure_2018_2019.json"

for p in [BLENDED_SHARE_JSON, DISTRICT_THRESHOLDS_JSON, GLOBAL_THRESHOLDS_JSON]:
    if not p.exists():
        raise FileNotFoundError(f"[FATAL] required artifact missing: {p.resolve()}")


DateLike = Union[str, datetime, date, pd.Timestamp]


def to_month_start(dt: DateLike) -> pd.Timestamp:
    t = pd.to_datetime(dt)
    return pd.Timestamp(year=int(t.year), month=int(t.month), day=1)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# -------------------------
# Small perf/stability improvement:
# cache arrivals DF so every request doesn't reload CSV
# -------------------------
_ARRIVALS_DF_CACHE: Optional[pd.DataFrame] = None


def _load_arrivals_df() -> pd.DataFrame:
    global _ARRIVALS_DF_CACHE
    if _ARRIVALS_DF_CACHE is not None:
        return _ARRIVALS_DF_CACHE

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

    _ARRIVALS_DF_CACHE = df[["month_start", "arrivals"]].copy()
    return _ARRIVALS_DF_CACHE


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
    Sustainability-friendly crowd mapping using percentiles (pressure-based thresholds):

      <= p25 -> Low
      <= p50 -> Moderate
      <= p75 -> High
      <= p90 -> VeryHigh
      >  p90 -> Extreme

    Why this is better:
    - Avoids "always VeryHigh" behavior when value is just slightly above p75.
    - Gives a defendable Extreme band for outlier months.
    """
    p25 = thresholds.get("p25")
    p50 = thresholds.get("p50")
    p75 = thresholds.get("p75")
    p90 = thresholds.get("p90")

    # If thresholds are incomplete, avoid lying
    if p25 is None or p50 is None or p75 is None:
        return "Unknown"

    if value <= p25:
        return "Low"
    if value <= p50:
        return "Moderate"
    if value <= p75:
        return "High"

    # If p90 isn't available, keep backward compatibility
    if p90 is None:
        return "VeryHigh"

    if value <= p90:
        return "VeryHigh"
    return "Extreme"


import math

def _compute_crowd_risk(adjusted_pressure: float, thresholds: Dict[str, float]) -> Dict[str, float]:
    """
    Smooth crowd risk using ratio = pressure/p90 (no hard saturation).
    - ratio=1.0 -> 0.50
    - ratio=1.3 -> ~0.77
    - ratio=1.6 -> ~0.90
    """
    p90 = thresholds.get("p90")
    if not p90 or p90 <= 0:
        return {"pressure_vs_p90": float("nan"), "crowd_risk_0_1": 0.5}

    pressure = float(adjusted_pressure)
    ratio = pressure / float(p90)

    k = 4.0  # steepness
    risk = 1.0 / (1.0 + math.exp(-k * (ratio - 1.0)))  # sigmoid centered at 1.0

    return {"pressure_vs_p90": float(ratio), "crowd_risk_0_1": float(risk)}


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

    # ---- Domestic pressure adjustment ----
    DOMESTIC_MULTIPLIERS_JSON = ROOT_DATA_ROOT / "clean/crowd/domestic_multipliers.json"
    domestic_multipliers = _load_json(DOMESTIC_MULTIPLIERS_JSON)

    month = int(month_start.month)
    domestic_factor = float(domestic_multipliers.get(str(month), 1.0))

    adjusted_pressure = expected * domestic_factor

    # Use district thresholds if available, else global
    # keep district thresholds only for label (optional)
    th_label = district_thresholds.get(district) or global_thresholds
    p25 = float(global_thresholds.get("p25", 0))
    p90 = float(global_thresholds.get("p90", 0))

    print(
        f"[CROWD-DBG] {district} {month_start.date()} "
        f"share={share:.6f} total={total_arrivals:.0f} dom={domestic_factor:.2f} "
        f"pressure={adjusted_pressure:.0f} p25={p25:.0f} p90={p90:.0f} "
        f"pressure/p90={(adjusted_pressure/p90 if p90 else float('nan')):.2f}"
)

    # ✅ use GLOBAL thresholds for risk so districts differ
    risk_metrics = _compute_crowd_risk(adjusted_pressure, global_thresholds)

    crowd_risk = risk_metrics["crowd_risk_0_1"]
    pressure_vs_p90 = risk_metrics["pressure_vs_p90"]

    level = crowd_level_from_thresholds(adjusted_pressure, th_label)


    return {
        "status": "ok",
        "district": district,
        "month_start": str(month_start.date()),
        "arrivals_source": arrivals_source,
        "total_arrivals_month": float(total_arrivals),
        "district_share_blended": share,
        "foreign_only_district_visitors": expected,
        "domestic_multiplier_used": domestic_factor,
        "total_district_pressure": adjusted_pressure,
        "crowd_level": level,
        "pressure_vs_p90": pressure_vs_p90,
        "crowd_risk_0_1": crowd_risk,
        "thresholds_used": "district_for_label + global_for_risk",
        "thresholds_label": th_label,
        "thresholds_risk": global_thresholds,
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
