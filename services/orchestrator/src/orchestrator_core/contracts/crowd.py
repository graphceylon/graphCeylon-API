#src/orchestrator_core/contracts/crowd.py:


from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from .common import BaseLocationTimeRequest


class CrowdForecastRequest(BaseLocationTimeRequest):
    intent: str = "crowd_forecast"
    poi_name: Optional[str] = None


class CrowdForecastResponse(BaseModel):
    poi_id: str
    poi_title: Optional[str] = None
    district: Optional[str] = None
    province: Optional[str] = None
    month_start: str

    total_foreign_arrivals_month: Optional[float] = None
    foreign_in_target_district_mean: Optional[float] = None
    foreign_to_poi_mean: Optional[float] = None
    domestic_multiplier_used: Optional[float] = None

    estimated_monthly_visitors_mean: Optional[float] = None
    avg_daily_visitors_mean: Optional[float] = None

    capacity_per_day: Optional[float] = None
    crowd_index_mean: Optional[float] = None

    thresholds: Optional[Dict[str, float]] = None
    crowd_level: str

    drivers: Optional[List[str]] = None
    uncertainty: Optional[Dict[str, Any]] = None
    arrivals_source: Optional[str] = None

