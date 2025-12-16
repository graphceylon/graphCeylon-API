from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from .common import BaseLocationTimeRequest


class SustainabilityForecastRequest(BaseLocationTimeRequest):
    intent: str = "forecast_sustainability"

    poi_name: Optional[str] = None
    eco_preference: Optional[str] = None   # low | medium | high


class SustainabilityForecastResponse(BaseModel):
    location: str
    start_date: Optional[str]
    end_date: Optional[str]

    sustainability_score: float            # 0–1
    sustainability_level: str              # low | medium | high
    summary: str

    breakdown: Dict[str, Any] = {}          # crowd, weather, capacity, eco-risk
