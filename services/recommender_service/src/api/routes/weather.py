from __future__ import annotations

from typing import Optional, Literal, Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.weather.logic import forecast_weather_logic

router = APIRouter()

TimeOfDay = Optional[Literal["morning", "afternoon", "evening"]]
WeatherSource = Literal["short_range_api_daily", "long_range_models_monthly"]


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


class WeatherPoint(BaseModel):
    ds: str  # "YYYY-MM-DD" (day) or "YYYY-MM-01" (month start)
    temp_c: Optional[float] = None
    condition: Optional[str] = None
    rain_risk: Optional[str] = None
    mean_mm: Optional[float] = None
    min_c: Optional[float] = None
    max_c: Optional[float] = None


class WeatherForecastResponse(BaseModel):
    city: str
    country: str
    start_date: str
    end_date: str
    time_of_day: TimeOfDay = None

    source: WeatherSource
    forecast_summary: str

    daily: Optional[List[WeatherPoint]] = None
    monthly: Optional[List[WeatherPoint]] = None

    warnings: List[str] = []


def _normalize_source(raw_source: str) -> WeatherSource:
    """
    Map internal sources (openweather, sarima, climatology...) to stable inter-service contract sources.
    """
    if raw_source in ("openweather_5day_daily", "openweather_daily", "api_daily"):
        return "short_range_api_daily"
    if raw_source in ("long_range_models_monthly", "sarima_monthly", "climatology_monthly"):
        return "long_range_models_monthly"

    # Safe default (don’t crash the API if a new internal label appears)
    return "long_range_models_monthly"


@router.post("/forecast/weather", response_model=WeatherForecastResponse)
def forecast_weather(req: WeatherForecastRequest):
    try:
        fc: Dict[str, Any] = forecast_weather_logic(req.model_dump())

        raw_source = str(fc.get("source", "long_range_models_monthly"))
        source: WeatherSource = _normalize_source(raw_source)

        warnings: List[str] = []
        summary_parts: List[str] = []

        # ---------- LONG RANGE (MONTHLY) ----------
        monthly_points: List[WeatherPoint] = []
        if source == "long_range_models_monthly":
            debug = fc.get("debug", {}) or {}

            temp_note = (debug.get("temperature", {}) or {}).get("note")
            if temp_note:
                warnings.append(temp_note)

            rain_monthly = (debug.get("rainfall", {}) or {}).get("monthly", []) or []
            for m in rain_monthly:
                month_str = m.get("month")  # "YYYY-MM"
                if month_str:
                    monthly_points.append(
                        WeatherPoint(
                            ds=f"{month_str}-01",
                            condition=m.get("condition"),
                            rain_risk=m.get("rain_risk"),
                            mean_mm=m.get("mean_mm"),
                        )
                    )

            if monthly_points:
                first = monthly_points[0]
                if first.rain_risk:
                    summary_parts.append(f"{first.ds[:7]} rain risk is {first.rain_risk}")
                if first.mean_mm is not None:
                    summary_parts.append(f"mean rainfall ~{first.mean_mm:.0f}mm")

        # ---------- SHORT RANGE (DAILY) ----------
        daily_points: List[WeatherPoint] = []
        if source == "short_range_api_daily":
            # Your logic might return daily points either at top-level or inside debug.
            daily_raw = fc.get("daily") or fc.get("debug", {}).get("daily") or []
            for d in daily_raw:
                ds = d.get("ds") or d.get("date")  # support either key
                if not ds:
                    continue
                daily_points.append(
                    WeatherPoint(
                        ds=ds,
                        temp_c=d.get("temp_c") or d.get("temp"),
                        min_c=d.get("min_c"),
                        max_c=d.get("max_c"),
                        condition=d.get("condition") or d.get("weather"),
                        rain_risk=d.get("rain_risk"),
                    )
                )

            if daily_points:
                summary_parts.append("Short-range daily forecast from API")

        forecast_summary = ". ".join(summary_parts) if summary_parts else "Weather forecast generated."

        return WeatherForecastResponse(
            city=fc.get("city") or req.city or "",
            country=fc.get("country") or req.country or "",
            start_date=req.start_date or "",
            end_date=req.end_date or "",
            time_of_day=req.time_of_day,
            source=source,
            forecast_summary=forecast_summary,
            daily=daily_points if daily_points else [],
            monthly=monthly_points if monthly_points else [],
            warnings=warnings,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weather forecast failed: {e}")
