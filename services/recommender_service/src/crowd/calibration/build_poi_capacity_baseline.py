from __future__ import annotations

import json
import calendar
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from services.recommender_service.src.crowd.data.district_norm import norm_district
import pandas as pd 
import numpy as np

from configs.recommender_service.config import (
    CROWD_POI_CAPACITY_JSON,
    CROWD_DOMESTIC_MULTIPLIERS_JSON,
    CROWD_POI_PRIORS_JSON,
    DATA_CLEAN_DIR,
)

from services.recommender_service.src.crowd.poi_registry import load_pois, pois_by_district
try:
    # when running from repo root with PYTHONPATH="."
    from services.recommender_service.src.crowd.data.arrivals_loader import load_sltda_arrivals_monthly
except ModuleNotFoundError:
    # fallback if someone runs with PYTHONPATH="services/recommender_service"
    from crowd.data.arrivals_loader import load_sltda_arrivals_monthly



# ---------------------------
# Helpers
# ---------------------------

def _days_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def _iter_month_starts(start: date, end: date) -> List[date]:
    cur = date(start.year, start.month, 1)
    endm = date(end.year, end.month, 1)
    out: List[date] = []
    while cur <= endm:
        out.append(cur)
        y = cur.year + (cur.month // 12)
        m = (cur.month % 12) + 1
        cur = date(y, m, 1)
    return out


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_prob_map(m: Dict[str, float]) -> Dict[str, float]:
    s = float(sum(m.values()))
    if s <= 0:
        return {}
    return {k: float(v) / s for k, v in m.items()}


# ---------------------------
# Core builder
# ---------------------------

@dataclass(frozen=True)
class CapacityBuildConfig:
    baseline_years: Tuple[int, int] = (2018, 2019)
    percentile: float = 0.90
    district_share_file: Path = DATA_CLEAN_DIR.parent / "sustainability" / "district_pressure_share_2018_2019_from_sltda_prefs.json"


def build_estimated_daily_series_for_all_pois(cfg: CapacityBuildConfig) -> Dict[str, List[float]]:
    """
    Build estimated daily visitor series per POI across baseline months.
    Uses:
      - SLTDA foreign arrivals monthly (actual baseline)
      - district pressure share (2018_2019 prefs-derived)
      - POI priors (per-district distribution across POIs)
      - domestic multipliers (seasonality prior)
    """
    # Load POIs
    pois = load_pois()
    by_dist = pois_by_district(pois)

    # Load district shares for baseline (2018_2019)
    ds_obj = _load_json(cfg.district_share_file)
    district_share = (ds_obj.get("district_share") or {}) if isinstance(ds_obj, dict) else {}
    district_share = {norm_district(k): float(v) for k, v in district_share.items()}

    # Load POI priors (per district)
    poi_priors = _load_json(Path(CROWD_POI_PRIORS_JSON))
    # expected: {"matale":{"sigiriya":0.38, ...}, ...}
    poi_priors = {str(d).strip().lower(): (v or {}) for d, v in poi_priors.items()}

    # Load domestic multipliers
    dom = _load_json(Path(CROWD_DOMESTIC_MULTIPLIERS_JSON))
    # keys might be "1".."12"
    dom_mult = {int(k): float(v) for k, v in dom.items()} if dom else {}

    # Load arrivals and filter baseline years
    arr = load_sltda_arrivals_monthly().df.copy()
    arr = arr[(arr["year"] >= cfg.baseline_years[0]) & (arr["year"] <= cfg.baseline_years[1])]
    if arr.empty:
        raise ValueError(f"No arrivals rows for baseline years {cfg.baseline_years} in SLTDA arrivals CSV.")

    # Build month -> total arrivals
    month_to_total: Dict[date, int] = {}
    for _, r in arr.iterrows():
        dts = r["date"]
        if pd.isna(dts):
            continue
        ms = date(int(r["year"]), int(r["month"]), 1)
        month_to_total[ms] = int(r["arrivals"])

    # Build daily series per POI
    series: Dict[str, List[float]] = {p.poi_id: [] for p in pois}

    for month_start, total_arrivals in sorted(month_to_total.items()):
        days = _days_in_month(month_start)
        m = month_start.month

        # district expected foreign counts
        # (if district not in share table -> 0)
        for dist, pois_in_dist in by_dist.items():
            dist_key = dist.strip().lower()
            dist_share = float(district_share.get(dist_key, 0.0))
            foreign_in_dist = total_arrivals * dist_share

            # poi prior distribution within district
            pri = poi_priors.get(dist_key, {}) or {}
            pri = {str(k).strip().lower(): float(v) for k, v in pri.items()}
            pri = _normalize_prob_map(pri)

            # smoothing: if priors missing/empty, use uniform across POIs in district
            if not pri:
                if pois_in_dist:
                    uni = 1.0 / len(pois_in_dist)
                    pri = {p.poi_id: uni for p in pois_in_dist}

            # domestic multiplier prior
            dm = float(dom_mult.get(m, 1.0))

            for p in pois_in_dist:
                share_p = float(pri.get(p.poi_id, 0.0))
                foreign_to_poi = foreign_in_dist * share_p

                # total pressure (foreign * domestic multiplier prior)
                monthly_visitors = foreign_to_poi * max(1.0, dm)
                daily_visitors = monthly_visitors / float(days)

                series[p.poi_id].append(float(daily_visitors))

    return series


def build_capacity_json_from_series(series: Dict[str, List[float]], percentile: float) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for poi_id, vals in series.items():
        clean = [v for v in vals if v is not None and v >= 0]
        if not clean:
            out[poi_id] = 0.0
            continue
        out[poi_id] = float(np.quantile(np.array(clean, dtype=float), percentile))
    return out


def main() -> Dict[str, str]:
    cfg = CapacityBuildConfig()

    series = build_estimated_daily_series_for_all_pois(cfg)
    capacities = build_capacity_json_from_series(series, cfg.percentile)

    out_path = Path(CROWD_POI_CAPACITY_JSON)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(capacities, indent=2), encoding="utf-8")

    # Optional: save audit so you can cite baseline evidence
    audit_path = out_path.parent / "poi_capacity_baseline_audit.csv"
    import pandas as pd
    rows = []
    for poi_id, vals in series.items():
        rows.append({
            "poi_id": poi_id,
            "n_months": len(vals),
            "mean_daily": float(np.mean(vals)) if vals else 0.0,
            "p90_daily": float(capacities.get(poi_id, 0.0)),
        })
    pd.DataFrame(rows).sort_values("p90_daily", ascending=False).to_csv(audit_path, index=False)

    return {
        "status": "ok",
        "baseline_years": str(cfg.baseline_years),
        "percentile": str(cfg.percentile),
        "capacity_json": str(out_path),
        "audit_csv": str(audit_path),
        "poi_count": str(len(series)),
    }


if __name__ == "__main__":
    print(main())
