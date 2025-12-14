# src/orchestrator_core/contracts/weather.py

from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from .common import BaseLocationTimeRequest


class WeatherForecastRequest(BaseLocationTimeRequest):
    intent: str = "forecast_weather"


class WeatherForecastResponse(BaseModel):
    city: str
    start_date: str
    end_date: str
    time_of_day: Optional[str] = None
    forecast_summary: str
    daily: List[Dict[str, Any]]
