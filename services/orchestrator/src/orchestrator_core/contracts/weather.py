# src/orchestrator_core/contracts/weather.py

from typing import Optional, List, Literal
from pydantic import BaseModel
from .common import BaseLocationTimeRequest


class WeatherForecastRequest(BaseLocationTimeRequest):
    intent: str = "forecast_weather"


class WeatherPoint(BaseModel):
    ds: str  # "2025-12-01" (month) or "2025-12-15" (day)
    temp_c: Optional[float] = None
    condition: Optional[str] = None          # "Rain", "Clouds", etc.
    rain_risk: Optional[str] = None          # "Low"/"Medium"/"High" (or later float prob)
    mean_mm: Optional[float] = None          # useful for monthly climatology
    min_c: Optional[float] = None            # if API provides min/max
    max_c: Optional[float] = None


class WeatherForecastResponse(BaseModel):
    city: str
    country: str
    start_date: str
    end_date: str
    time_of_day: Optional[str] = None

    source: Literal["short_range_api_daily", "long_range_models_monthly"]
    forecast_summary: str

    daily: Optional[List[WeatherPoint]] = None
    monthly: Optional[List[WeatherPoint]] = None

    warnings: List[str] = []
