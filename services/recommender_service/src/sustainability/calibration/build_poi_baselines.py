from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import json
import pandas as pd

from configs.recommender_service.config import (
    SLTDA_ARRIVALS_MONTHLY_CSV,
    SUSTAINABILITY_POI_BASELINES_JSON,
    SUSTAINABILITY_POI_MONTHLY_BASELINES_JSON,
)

from services.recommender_service.src.crowd.poi_registry import load_pois
from services.recommender_service.src.crowd.inference.crowd_model import forecast_poi_crowd


print("[baseline] file loaded")


def _find_arrivals_column(cols: List[str]) -> Optional[str]:
    cols_l = [c.strip().lower() for c in cols]
    candidates = [
        "arrivals", "total_arrivals", "foreign_arrivals", "total_foreign_arrivals",
        "sltda_arrivals", "value", "count"
    ]
    for cand in candidates:
        if cand in cols_l:
            return cols[cols_l.index(cand)]
    return None


def load_monthly_arrivals(path: Path) -> Dict[date, int]:
    df = pd.read_csv(path)
    # try common date column names
    date_col = None
    for c in df.columns:
        if c.strip().lower() in ("date", "month", "ds"):
            date_col = c
            break
    if date_col is None:
        raise ValueError(f"No date column found in {path}. Columns={list(df.columns)}")

    arr_col = _find_arrivals_column(list(df.columns))
    if arr_col is None:
        raise ValueError(f"No arrivals column found in {path}. Columns={list(df.columns)}")

    df[date_col] = pd.to_datetime(df[date_col])
    out: Dict[date, int] = {}
    for d, a in zip(df[date_col], df[arr_col]):
        out[date(d.year, d.month, 1)] = int(a)
    return out


def _month_range(start: date, end: date) -> List[date]:
    cur = date(start.year, start.month, 1)
    out = []
    while cur <= end:
        out.append(cur)
        y = cur.year + (cur.month // 12)
        m = (cur.month % 12) + 1
        cur = date(y, m, 1)
    return out


def percentile(xs: List[float], p: float) -> float:
    if not xs:
        return 0.0
    xs2 = sorted(xs)
    k = int(round((len(xs2) - 1) * p))
    return float(xs2[max(0, min(k, len(xs2) - 1))])


def build_baselines(
    start: date,
    end: date,
    pcts: Tuple[float, ...] = (0.5, 0.75, 0.9),
    n_samples_calib: int = 80,   # IMPORTANT: smaller than 700
) -> Dict[str, Any]:
    arrivals_map = load_monthly_arrivals(SLTDA_ARRIVALS_MONTHLY_CSV)

    pois = load_pois()
    poi_ids = [p.poi_id for p in pois]

    months = _month_range(start, end)

    # collect time series: poi_id -> list of avg_daily
    series: Dict[str, List[Tuple[date, float]]] = {pid: [] for pid in poi_ids}

    for i, month_start in enumerate(months, 1):
        arrivals = arrivals_map.get(month_start)
        print(f"[baseline] month={month_start} arrivals={arrivals}")
        if arrivals <= 0:
            continue

        # run each poi for this month
        for pid in poi_ids:
            out = forecast_poi_crowd(
                poi_id=pid,
                month_start=month_start,
                total_foreign_arrivals_month=arrivals,
                n_samples=120,
                # speed: reduce MC samples via strength params + fewer samples in allocator if you add later
                # (for now we accept current internal n_samples=700; if you can, expose it)
            )
            if out.get("status") != "ok":
                continue
            avg_daily = float(out.get("avg_daily_visitors_mean") or 0.0)
            series[pid].append((month_start, avg_daily))

        if i % 6 == 0:
            print(f"[baseline] processed {i}/{len(months)} months")

    # overall baselines + monthly baselines
    poi_baselines: Dict[str, Any] = {}
    poi_monthly_baselines: Dict[str, Any] = {}

    for pid, points in series.items():
        values = [v for _, v in points if v > 0]
        poi_baselines[pid] = {f"p{int(p*100)}": percentile(values, p) for p in pcts}
        poi_baselines[pid]["n"] = len(values)

        # month-of-year baselines
        by_m: Dict[int, List[float]] = {}
        for d, v in points:
            if v <= 0:
                continue
            by_m.setdefault(d.month, []).append(v)

        poi_monthly_baselines[pid] = {}
        for m in range(1, 13):
            xs = by_m.get(m, [])
            poi_monthly_baselines[pid][str(m)] = {
                f"p{int(p*100)}": percentile(xs, p) for p in pcts
            }
            poi_monthly_baselines[pid][str(m)]["n"] = len(xs)

    return {
        "poi_baselines": poi_baselines,
        "poi_monthly_baselines": poi_monthly_baselines,
        "meta": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "pcts": list(pcts),
            "notes": [
                "Baselines are self-calibrated from your crowd model outputs (not official capacities).",
                "Use monthly baselines for season-aware sustainability scoring."
            ],
        },
    }


def main() -> str:
    print("[baseline] entered main()")
    data = build_baselines(
        start=date(2023, 1, 1),
        end=date(2025, 12, 1),
        pcts=(0.5, 0.75, 0.9),
    )

    SUSTAINABILITY_POI_BASELINES_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUSTAINABILITY_POI_BASELINES_JSON.write_text(
        json.dumps(data["poi_baselines"], indent=2), encoding="utf-8"
    )
    SUSTAINABILITY_POI_MONTHLY_BASELINES_JSON.write_text(
        json.dumps(data["poi_monthly_baselines"], indent=2), encoding="utf-8"
    )
    return f"OK -> {SUSTAINABILITY_POI_BASELINES_JSON} and {SUSTAINABILITY_POI_MONTHLY_BASELINES_JSON}"


if __name__ == "__main__":
    print(main())
