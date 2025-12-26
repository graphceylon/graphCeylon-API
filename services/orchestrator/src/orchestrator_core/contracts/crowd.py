#src/orchestrator_core/contracts/crowd.py:


from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from .common import BaseLocationTimeRequest


class CrowdForecastRequest(BaseLocationTimeRequest):
    intent: str = "crowd_forecast"
    poi_name: Optional[str] = None


class CrowdForecastResponse(BaseModel):
    location: str                 # city or poi_name chosen by service
    start_date: str
    end_date: str
    time_of_day: Optional[str] = None
    crowd_level: str              # "low" | "medium" | "high"
    confidence: Optional[float] = None
    summary: str
    daily: List[Dict[str, Any]] = []

