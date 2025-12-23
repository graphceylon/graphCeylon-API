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
    raw_source = (raw_source or "").strip()

    if raw_source in ("short_range_api_daily", "openweather_5day_daily", "openweather_daily", "api_daily"):
        return "short_range_api_daily"

    if raw_source in ("long_range_models_monthly", "sarima_monthly", "climatology_monthly"):
        return "long_range_models_monthly"

    # Safe default
    return "long_range_models_monthly"


def _to_daily_point(d: Dict[str, Any]) -> Optional[WeatherPoint]:
    """
    Accept BOTH schemas:
      A) public: ds,temp_c,min_c,max_c,mean_mm,rain_risk,condition
      B) internal: date,temp_avg,temp_min,temp_max,mean_mm,rain_risk,condition
    """
    if not isinstance(d, dict):
        return None

    ds = d.get("ds") or d.get("date")
    if not ds:
        return None

    temp_c = d.get("temp_c")
    if temp_c is None:
        temp_c = d.get("temp_avg")
    if temp_c is None:
        temp_c = d.get("temp")

    min_c = d.get("min_c")
    if min_c is None:
        min_c = d.get("temp_min")

    max_c = d.get("max_c")
    if max_c is None:
        max_c = d.get("temp_max")

    return WeatherPoint(
        ds=ds,
        temp_c=temp_c,
        min_c=min_c,
        max_c=max_c,
        condition=d.get("condition") or d.get("weather") or d.get("weather_main"),
        rain_risk=d.get("rain_risk"),
        mean_mm=d.get("mean_mm"),
    )


def _to_monthly_point(m: Dict[str, Any]) -> Optional[WeatherPoint]:
    """
    Accept BOTH schemas:
      A) public monthly points: ds or month+values
      B) internal build_monthly_weather: month,temp_avg,mean_mm,rain_risk,condition
    """
    if not isinstance(m, dict):
        return None

    ds = m.get("ds")
    if not ds:
        # build_monthly_weather returns month = "YYYY-MM"
        month = m.get("month")
        if month:
            ds = f"{month}-01"
    if not ds:
        return None

    temp_c = m.get("temp_c")
    if temp_c is None:
        temp_c = m.get("temp_avg")

    return WeatherPoint(
        ds=ds,
        temp_c=temp_c,
        min_c=m.get("min_c"),
        max_c=m.get("max_c"),
        condition=m.get("condition") or "Unknown",
        rain_risk=m.get("rain_risk"),
        mean_mm=m.get("mean_mm"),
    )


@router.post("/forecast/weather", response_model=WeatherForecastResponse)
def forecast_weather(req: WeatherForecastRequest):
    try:
        fc: Dict[str, Any] = forecast_weather_logic(req.model_dump())

        raw_source = str(fc.get("source", "long_range_models_monthly"))
        source: WeatherSource = _normalize_source(raw_source)

        # Collect warnings from logic + debug notes (if any)
        warnings: List[str] = []
        if isinstance(fc.get("warnings"), list):
            warnings.extend([str(x) for x in fc.get("warnings") if x])

        debug = fc.get("debug", {}) or {}
        if isinstance(debug, dict):
            temp_note = (debug.get("temperature", {}) or {}).get("note")
            if temp_note:
                warnings.append(str(temp_note))
            rain_note = (debug.get("rainfall", {}) or {}).get("note")
            if rain_note:
                warnings.append(str(rain_note))

        # ---------- DAILY ----------
        daily_points: List[WeatherPoint] = []
        daily_raw = fc.get("daily") or []
        if isinstance(daily_raw, list):
            for d in daily_raw:
                p = _to_daily_point(d)
                if p:
                    daily_points.append(p)

        # ---------- MONTHLY ----------
        monthly_points: List[WeatherPoint] = []
        # ✅ MOST IMPORTANT FIX: use fc["monthly"] FIRST (do not rely on debug)
        monthly_raw = fc.get("monthly") or []
        if isinstance(monthly_raw, list):
            for m in monthly_raw:
                p = _to_monthly_point(m)
                if p:
                    monthly_points.append(p)

        # fallback: if monthly empty but debug has rainfall monthly, use that
        if not monthly_points and isinstance(debug, dict):
            rain_monthly = (debug.get("rainfall", {}) or {}).get("monthly", []) or []
            if isinstance(rain_monthly, list):
                for m in rain_monthly:
                    month_str = m.get("month")
                    if month_str:
                        monthly_points.append(
                            WeatherPoint(
                                ds=f"{month_str}-01",
                                condition=m.get("condition"),
                                rain_risk=m.get("rain_risk"),
                                mean_mm=m.get("mean_mm"),
                            )
                        )

        # ---------- SUMMARY ----------
        summary_parts: List[str] = []
        if source == "short_range_api_daily":
            summary_parts.append("Short-range daily forecast from API")
        else:
            summary_parts.append("Long-range monthly forecast from SARIMA + climatology")

        if daily_points and daily_points[0].temp_c is not None:
            summary_parts.append(f"{daily_points[0].ds} avg ~{daily_points[0].temp_c:.1f}°C")

        if monthly_points and monthly_points[0].rain_risk:
            summary_parts.append(f"{monthly_points[0].ds[:7]} rain risk {monthly_points[0].rain_risk}")

        forecast_summary = ". ".join(summary_parts) if summary_parts else "Weather forecast generated."

        return WeatherForecastResponse(
            city=str(fc.get("city") or req.city or ""),
            country=str(fc.get("country") or req.country or ""),
            start_date=str(fc.get("start_date") or req.start_date or ""),
            end_date=str(fc.get("end_date") or req.end_date or ""),
            time_of_day=req.time_of_day,
            source=source,
            forecast_summary=forecast_summary,
            daily=daily_points,
            monthly=monthly_points,
            warnings=warnings,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weather forecast failed: {type(e).__name__}: {e}")
