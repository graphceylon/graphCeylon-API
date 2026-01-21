from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from configs.recommender_service.config import (
    SLTDA_ARRIVALS_MONTHLY_CSV,
    DATA_CLEAN_DIR,
)

from services.recommender_service.src.crowd.data.arrivals_loader import load_sltda_arrivals_monthly
from services.recommender_service.src.crowd.data.arrivals_resolver import resolve_total_foreign_arrivals_month
from services.recommender_service.src.crowd.inference.crowd_model import forecast_poi_crowd
from services.recommender_service.src.crowd.poi_registry import load_pois


@dataclass(frozen=True)
class MonthlyCapacityConfig:
    baseline_years: Tuple[int, int] = (2018, 2019)
    percentile: float = 0.90
    out_json: Path = DATA_CLEAN_DIR.parent / "sustainability" / "poi_capacity_monthly_baseline.json"
    out_csv: Path = DATA_CLEAN_DIR.parent / "sustainability" / "poi_capacity_monthly_baseline.csv"


def _iter_month_starts(start: date, end: date) -> List[date]:
    cur = date(start.year, start.month, 1)
    end_m = date(end.year, end.month, 1)
    out: List[date] = []
    while cur <= end_m:
        out.append(cur)
        y = cur.year + (cur.month // 12)
        m = (cur.month % 12) + 1
        cur = date(y, m, 1)
    return out


def _baseline_months(arrivals_df: pd.DataFrame, years: Tuple[int, int]) -> List[date]:
    base = arrivals_df[(arrivals_df["year"] >= years[0]) & (arrivals_df["year"] <= years[1])].copy()
    if base.empty:
        raise ValueError(f"No arrivals rows found for baseline years={years} in SLTDA arrivals CSV.")
    months = sorted(base["date"].dt.to_period("M").dt.to_timestamp().dt.date.unique().tolist())
    # ensure month-start
    return [date(d.year, d.month, 1) for d in months]


def build_monthly_series_for_poi(poi_id: str, months: List[date]) -> List[float]:
    """
    For each baseline month, call your crowd model and collect estimated_monthly_visitors_mean.
    """
    series: List[float] = []
    for m in months:
        # Prefer resolver (forecast) but for baseline years it should come from historical file anyway
        res = resolve_total_foreign_arrivals_month(m)
        out = forecast_poi_crowd(
            poi_id=poi_id,
            month_start=m,
            total_foreign_arrivals_month=int(res.arrivals),
        )
        if out.get("status") != "ok":
            series.append(0.0)
            continue
        v = out.get("estimated_monthly_visitors_mean")
        try:
            series.append(float(v) if v is not None else 0.0)
        except Exception:
            series.append(0.0)
    return series


def main() -> Dict[str, object]:
    cfg = MonthlyCapacityConfig()

    # Load baseline months from SLTDA arrivals file (2018–2019)
    arr = load_sltda_arrivals_monthly(Path(SLTDA_ARRIVALS_MONTHLY_CSV)).df.copy()
    arr["date"] = pd.to_datetime(arr["date"], errors="coerce")
    arr = arr.dropna(subset=["date"])
    months = _baseline_months(arr, cfg.baseline_years)

    pois = load_pois()
    poi_ids = [p.poi_id for p in pois]

    rows = []
    cap_map: Dict[str, float] = {}

    for pid in poi_ids:
        series = build_monthly_series_for_poi(pid, months)
        series = [x for x in series if x is not None]
        if len(series) == 0:
            pctl = 0.0
            mu = 0.0
        else:
            mu = float(np.mean(series))
            pctl = float(np.quantile(np.array(series, dtype=float), cfg.percentile))

        # capacity must not be 0 if mean is non-zero; still allow 0 for truly empty series
        cap_map[pid] = float(round(pctl, 3))

        rows.append(
            {
                "poi_id": pid,
                "n_months": len(series),
                "mean_monthly": round(mu, 3),
                f"p{int(cfg.percentile*100)}_monthly": round(pctl, 3),
            }
        )

    cfg.out_json.parent.mkdir(parents=True, exist_ok=True)
    cfg.out_json.write_text(json.dumps(
        {
            "baseline_years": list(cfg.baseline_years),
            "percentile": cfg.percentile,
            "capacity_monthly_by_poi": cap_map,
            "note": "Monthly capacity is an operational threshold derived as a percentile of baseline estimated monthly visitors (not official site capacity).",
        },
        indent=2
    ), encoding="utf-8")

    pd.DataFrame(rows).to_csv(cfg.out_csv, index=False)

    return {
        "status": "ok",
        "poi_count": len(poi_ids),
        "baseline_months": len(months),
        "out_json": str(cfg.out_json),
        "out_csv": str(cfg.out_csv),
        "years": cfg.baseline_years,
        "percentile": cfg.percentile,
    }


if __name__ == "__main__":
    print(main())
