from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Literal, Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.weather.logic import forecast_weather_logic

router = APIRouter()

TimeOfDay = Optional[Literal["morning", "afternoon", "evening"]]


class WeatherForecastRequest(BaseModel):
    intent: str = Field(default="forecast_weather")
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    raw_text: str

    city: Optional[str] = None
    country: Optional[str] = None

    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None    # YYYY-MM-DD
    time_of_day: TimeOfDay = None


class WeatherForecastResponse(BaseModel):
    status: str
    message: str
    forecast: Dict[str, Any]


@router.post("/forecast/weather", response_model=WeatherForecastResponse)
def forecast_weather(req: WeatherForecastRequest):
    try:
        fc = forecast_weather_logic(req.model_dump())
        return WeatherForecastResponse(
            status="ok",
            message="Weather forecast generated",
            forecast=fc,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weather forecast failed: {e}")
