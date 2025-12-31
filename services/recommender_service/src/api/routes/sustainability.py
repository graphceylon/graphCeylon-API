from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
import json
from pathlib import Path

from services.recommender_service.src.sustainability.district_crowd.predict import (
    predict_district_crowd,
    predict_attraction_crowd,
)

# ✅ Use the SAME weather logic you already use in your weather route
from src.weather.logic import forecast_weather_logic

# ✅ Your scorer file (you already have this in your code snippet)

from services.recommender_service.src.sustainability.district_crowd.sustainability_score import compute_sustainability_score
from services.recommender_service.src.sustainability.risk_maps import rain_risk_to_0_1
from services.recommender_service.src.sustainability.district_city_map import district_to_city
from src.weather.logic import forecast_weather_logic

router = APIRouter(prefix="/sustainability", tags=["Sustainability"])


class DistrictCrowdRequest(BaseModel):
    district: str = Field(..., example="Matale")
    date: str = Field(..., example="2026-05-10")


class AttractionCrowdRequest(BaseModel):
    attraction_id: str = Field(..., example="knuckles_range")
    date: str = Field(..., example="2026-05-10")


# ✅ NEW request models for scores
class DistrictScoreRequest(BaseModel):
    district: str = Field(..., example="Colombo")
    date: str = Field(..., example="2026-05-10")
    city: Optional[str] = Field(default=None, example="Colombo")  # for rain
    country: Optional[str] = Field(default="Sri Lanka", example="Sri Lanka")
    eco_preference: float = Field(default=0.5, ge=0.0, le=1.0, example=0.7)


class AttractionScoreRequest(BaseModel):
    attraction_id: str = Field(..., example="colombo")
    date: str = Field(..., example="2026-05-10")
    city: Optional[str] = Field(default=None, example="Colombo")
    country: Optional[str] = Field(default="Sri Lanka", example="Sri Lanka")
    eco_preference: float = Field(default=0.5, ge=0.0, le=1.0, example=0.7)

class RankAttractionsRequest(BaseModel):
    date: str
    country: str = "Sri Lanka"
    eco_preference: float = 0.5
    limit: int = 10
    district: Optional[str] = None  # optional filter


def _rain_risk_str_to_0_1(risk: Optional[str]) -> float:
    """
    Convert your weather risk labels -> numeric risk (0..1).
    Keep it simple + defensible.
    """
    r = (risk or "").strip().lower()
    if r == "low":
        return 0.2
    if r == "medium":
        return 0.5
    if r == "high":
        return 0.8
    return 0.5  # unknown -> neutral


def _get_rain_risk_for_date(city: str, country: str, date_str: str) -> Dict[str, Any]:
    """
    Calls your existing forecast_weather_logic and extracts a rain risk.
    For far future dates, your logic returns MONTHLY points.
    We’ll prefer monthly[0].rain_risk if present, else fallback safe.
    """
    payload = {
        "city": city,
        "country": country,
        "start_date": date_str,
        "end_date": date_str,
        "time_of_day": None,
    }
    fc = forecast_weather_logic(payload)

    # Prefer MONTHLY for long-range
    monthly = fc.get("monthly") or []
    if isinstance(monthly, list) and monthly:
        rain_risk = monthly[0].get("rain_risk")
        return {
            "weather_source": fc.get("source"),
            "rain_risk": rain_risk,
            "rain_risk_0_1": _rain_risk_str_to_0_1(rain_risk),
            "weather_point": monthly[0],
        }

    # Else DAILY
    daily = fc.get("daily") or []
    if isinstance(daily, list) and daily:
        rain_risk = daily[0].get("rain_risk")
        return {
            "weather_source": fc.get("source"),
            "rain_risk": rain_risk,
            "rain_risk_0_1": _rain_risk_str_to_0_1(rain_risk),
            "weather_point": daily[0],
        }

    # fallback
    return {
        "weather_source": fc.get("source"),
        "rain_risk": None,
        "rain_risk_0_1": 0.5,
        "weather_point": None,
        "warning": "No daily/monthly points returned; defaulted rain risk to 0.5",
    }


@router.get("/district-crowd")
def district_crowd_get(
    district: str = Query(..., description="District name, e.g., Matale"),
    date: str = Query(..., description="Any date within target month, e.g., 2026-05-10"),
) -> Dict[str, Any]:
    try:
        return predict_district_crowd(district, date)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Missing artifact/file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/district-crowd")
def district_crowd_post(payload: DistrictCrowdRequest) -> Dict[str, Any]:
    try:
        return predict_district_crowd(payload.district, payload.date)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Missing artifact/file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attraction-crowd")
def attraction_crowd_get(
    attraction_id: str = Query(..., description="attraction_id from attractions_clean.json"),
    date: str = Query(..., description="Any date within target month, e.g., 2026-05-10"),
) -> Dict[str, Any]:
    try:
        return predict_attraction_crowd(attraction_id, date)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Missing artifact/file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/attraction-crowd")
def attraction_crowd_post(payload: AttractionCrowdRequest) -> Dict[str, Any]:
    try:
        return predict_attraction_crowd(payload.attraction_id, payload.date)
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Missing artifact/file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# ✅ NEW: District Sustainability Score
# =========================
@router.get("/district-score")
def district_score_get(
    district: str = Query(...),
    date: str = Query(...),
    city: Optional[str] = Query(None, description="City for weather (defaults to district)"),
    country: str = Query("Sri Lanka"),
    eco_preference: float = Query(0.5, ge=0.0, le=1.0),
) -> Dict[str, Any]:
    try:
        crowd = predict_district_crowd(district, date)

        # Use city if provided, else district
        city_final = (city or district).strip()

        weather = _get_rain_risk_for_date(city_final, country, date)

        crowd_risk = float(crowd.get("crowd_risk_0_1", 0.5))
        rain_risk_0_1 = float(weather["rain_risk_0_1"])

        score = compute_sustainability_score(
            crowd_risk_0_1=crowd_risk,
            rain_risk_0_1=rain_risk_0_1,
            eco_preference=eco_preference,
        )

        return {
            "status": "ok",
            "district": crowd.get("district", district),
            "date": date,
            "month_start": crowd.get("month_start"),
            "eco_preference": eco_preference,
            "crowd": crowd,
            "weather": weather,
            "sustainability": score,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Missing artifact/file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/district-score")
def district_score_post(payload: DistrictScoreRequest) -> Dict[str, Any]:
    try:
        crowd = predict_district_crowd(payload.district, payload.date)

        city_final = (payload.city or payload.district).strip()
        weather = _get_rain_risk_for_date(city_final, payload.country or "Sri Lanka", payload.date)

        crowd_risk = float(crowd.get("crowd_risk_0_1", 0.5))
        rain_risk_0_1 = float(weather["rain_risk_0_1"])

        score = compute_sustainability_score(
            crowd_risk_0_1=crowd_risk,
            rain_risk_0_1=rain_risk_0_1,
            eco_preference=payload.eco_preference,
        )

        return {
            "status": "ok",
            "district": crowd.get("district", payload.district),
            "date": payload.date,
            "month_start": crowd.get("month_start"),
            "eco_preference": payload.eco_preference,
            "crowd": crowd,
            "weather": weather,
            "sustainability": score,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Missing artifact/file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# ✅ NEW: Attraction Sustainability Score
# =========================
@router.get("/attraction-score")
def attraction_score_get(
    attraction_id: str = Query(...),
    date: str = Query(...),
    city: Optional[str] = Query(None, description="City for weather (defaults to attraction district if present)"),
    country: str = Query("Sri Lanka"),
    eco_preference: float = Query(0.5, ge=0.0, le=1.0),
) -> Dict[str, Any]:
    try:
        crowd = predict_attraction_crowd(attraction_id, date)

        # If caller didn’t pass city, try district from crowd output
        district_from_crowd = crowd.get("district") or ""
        city_final = (city or district_from_crowd or "Colombo").strip()

        weather = _get_rain_risk_for_date(city_final, country, date)

        crowd_risk = float(crowd.get("crowd_risk_0_1", 0.5))
        rain_risk_0_1 = float(weather["rain_risk_0_1"])

        score = compute_sustainability_score(
            crowd_risk_0_1=crowd_risk,
            rain_risk_0_1=rain_risk_0_1,
            eco_preference=eco_preference,
        )

        return {
            "status": "ok",
            "attraction_id": attraction_id,
            "attraction_title": crowd.get("attraction_title"),
            "district": crowd.get("district"),
            "date": date,
            "month_start": crowd.get("month_start"),
            "eco_preference": eco_preference,
            "crowd": crowd,
            "weather": weather,
            "sustainability": score,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Missing artifact/file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/attraction-score")
def attraction_score_post(payload: AttractionScoreRequest) -> Dict[str, Any]:
    try:
        crowd = predict_attraction_crowd(payload.attraction_id, payload.date)

        district_from_crowd = crowd.get("district") or ""
        city_final = (payload.city or district_from_crowd or "Colombo").strip()

        weather = _get_rain_risk_for_date(city_final, payload.country or "Sri Lanka", payload.date)

        crowd_risk = float(crowd.get("crowd_risk_0_1", 0.5))
        rain_risk_0_1 = float(weather["rain_risk_0_1"])

        score = compute_sustainability_score(
            crowd_risk_0_1=crowd_risk,
            rain_risk_0_1=rain_risk_0_1,
            eco_preference=payload.eco_preference,
        )

        return {
            "status": "ok",
            "attraction_id": payload.attraction_id,
            "attraction_title": crowd.get("attraction_title"),
            "district": crowd.get("district"),
            "date": payload.date,
            "month_start": crowd.get("month_start"),
            "eco_preference": payload.eco_preference,
            "crowd": crowd,
            "weather": weather,
            "sustainability": score,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Missing artifact/file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rank-attractions")
def rank_attractions(payload: RankAttractionsRequest) -> Dict[str, Any]:
    try:
        # reuse same attractions file used in predict.py
        from services.recommender_service.src.sustainability.district_crowd.predict import ATTRACTIONS_JSON

        obj = json.loads(Path(ATTRACTIONS_JSON).read_text(encoding="utf-8"))

        # normalize list
        attractions = obj.get("attractions", obj) if isinstance(obj, dict) else obj
        if not isinstance(attractions, list):
            raise ValueError("Invalid attractions_clean.json format")

        out = []
        for a in attractions:
            if not isinstance(a, dict):
                continue

            district = a.get("district")
            if payload.district and (district or "").strip().lower() != payload.district.strip().lower():
                continue

            aid = a.get("attraction_id") or a.get("poi_id") or a.get("id")
            if not aid:
                continue

            crowd = predict_attraction_crowd(str(aid), payload.date)

            # weather city based on district
            city = district_to_city(crowd.get("district", district or ""))
            weather = forecast_weather_logic({
                "city": city,
                "country": payload.country,
                "start_date": payload.date,
                "end_date": payload.date,
                "time_of_day": None,
            })

            rain_risk = None
            if weather.get("daily"):
                rain_risk = (weather["daily"][0] or {}).get("rain_risk")
            elif weather.get("monthly"):
                rain_risk = (weather["monthly"][0] or {}).get("rain_risk")

            rain_risk_0_1 = rain_risk_to_0_1(rain_risk)

            score = compute_sustainability_score(
                crowd_risk_0_1=float(crowd.get("crowd_risk_0_1", 0.5)),
                rain_risk_0_1=float(rain_risk_0_1),
                eco_preference=float(payload.eco_preference),
            )

            out.append({
                "attraction_id": str(aid),
                "title": a.get("title") or a.get("name") or str(aid),
                "district": crowd.get("district", district),
                "crowd_level": crowd.get("crowd_level"),
                "crowd_risk_0_1": crowd.get("crowd_risk_0_1"),
                "rain_risk": rain_risk,
                "rain_risk_0_1": rain_risk_0_1,
                "sustainability": score,
            })

        # sort best first
        out.sort(key=lambda x: float(x["sustainability"]["score_0_1"]), reverse=True)

        return {
            "status": "ok",
            "date": payload.date,
            "eco_preference": float(payload.eco_preference),
            "count": len(out),
            "top": out[: max(1, int(payload.limit))],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))