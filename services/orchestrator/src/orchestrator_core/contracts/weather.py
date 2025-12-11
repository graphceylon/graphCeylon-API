# src/orchestrator_core/contracts/weather.py

from typing import Optional
from pydantic import BaseModel


class WeatherForecastRequest(BaseModel):
    intent: str  # e.g. "forecast_weather"

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    raw_text: str

    city: Optional[str] = None
    country: Optional[str] = None

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    time_of_day: Optional[str] = None
