from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional, Tuple, List, Any


@dataclass(frozen=True)
class CrowdInputs:
    poi_id: str
    month_start: date
    total_foreign_arrivals_month: int

    # Evidence (optional): district->count (telecom 2024 totals)
    telecom_district_counts: Optional[Dict[str, float]] = None

    # Priors (optional):
    # region_priors: {"cultural_triangle":0.289, ...}
    region_priors: Optional[Dict[str, float]] = None

    # poi_priors: {"matale":{"sigiriya":0.38, ...}, ...}
    poi_priors: Optional[Dict[str, Dict[str, float]]] = None


@dataclass(frozen=True)
class CrowdResult:
    status: str
    poi_id: str
    poi_title: str
    month_start: str
    crowd_index_mean: float
    crowd_level: str
    avg_daily_visitors_mean: float
    capacity_per_day: float
    drivers: List[str]
    uncertainty: Dict[str, Any]
