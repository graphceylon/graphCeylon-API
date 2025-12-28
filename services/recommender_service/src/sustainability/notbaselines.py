from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np

from configs.recommender_service.config import SUSTAINABILITY_POI_BASELINES_JSON
BASELINES_PATH = SUSTAINABILITY_POI_BASELINES_JSON


from services.recommender_service.src.crowd.poi_registry import load_pois
from services.recommender_service.src.crowd.data.arrivals_resolver import resolve_total_foreign_arrivals_month
from services.recommender_service.src.crowd.inference.crowd_model import forecast_poi_crowd




@dataclass(frozen=True)
class POIBaseline:
    p50: float
    p75: float
    p90: float
    p95: float
    n: int


def load_poi_baselines(path: Path = BASELINES_PATH) -> Dict[str, POIBaseline]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, POIBaseline] = {}
    for poi_id, v in raw.items():
        out[poi_id] = POIBaseline(
            p50=float(v["p50"]),
            p75=float(v["p75"]),
            p90=float(v["p90"]),
            n=int(v.get("n", 0)),
        )
    return out


def save_poi_baselines(b: Dict[str, POIBaseline], path: Path = BASELINES_PATH) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        k: {"p50": v.p50, "p75": v.p75, "p90": v.p90, "p95": v.p95, "n": v.n}
        for k, v in b.items()
    }
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


# def _month_starts(start: date, months: int) -> List[date]:
#     y, m = start.year, start.month
#     out: List[date] = []
#     for i in range(months):
#         mm = m + i
#         yy = y + (mm - 1) // 12
#         mo = ((mm - 1) % 12) + 1
#         out.append(date(yy, mo, 1))
#     return out


# def build_poi_baselines_percentiles(
#     horizon_months: int = 48,
#     start_month: Optional[date] = None,
# ) -> Dict[str, POIBaseline]:
#     """
#     Self-calibrating baselines:
#     For each POI, run your crowd model across a horizon and compute P50/P75/P90/P95
#     using avg_daily_visitors_mean.
#     """
#     if start_month is None:
#         today = date.today()
#         start_month = date(today.year, today.month, 1)

#     pois = load_pois()
#     values: Dict[str, List[float]] = {p.poi_id: [] for p in pois}

#     months = _month_starts(start_month, horizon_months)

#     for d in months:
#         arrivals_res = resolve_total_foreign_arrivals_month(d)
#         arrivals = int(arrivals_res.arrivals)

#         for p in pois:
#             out = forecast_poi_crowd(
#                 poi_id=p.poi_id,
#                 month_start=d,
#                 total_foreign_arrivals_month=arrivals,
#             )
#             if out.get("status") != "ok":
#                 continue
#             v = out.get("avg_daily_visitors_mean")
#             if v is None:
#                 continue
#             values[p.poi_id].append(float(v))

#     baselines: Dict[str, POIBaseline] = {}
#     for poi_id, xs in values.items():
#         if len(xs) < 8:
#             continue
#         arr = np.array(xs, dtype=float)
#         baselines[poi_id] = POIBaseline(
#             p50=float(np.percentile(arr, 50)),
#             p75=float(np.percentile(arr, 75)),
#             p90=float(np.percentile(arr, 90)),
#             p95=float(np.percentile(arr, 95)),
#             n=int(len(xs)),
#         )

#     return baselines
