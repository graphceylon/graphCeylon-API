from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
import json
from pathlib import Path

from services.recommender_service.src.sustainability.district_crowd.predict import (
    predict_district_crowd,
    predict_attraction_crowd,
)

# ✅ Use the SAME weather logic you already use in your weather route
from src.weather.logic import forecast_weather_logic

# ✅ Your scorer file
from services.recommender_service.src.sustainability.district_crowd.sustainability_score import (
    compute_sustainability_score,
)
from services.recommender_service.src.sustainability.risk_maps import rain_risk_to_0_1
from services.recommender_service.src.sustainability.district_city_map import district_to_city

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
    """
    try:
        v = rain_risk_to_0_1(risk)
        return max(0.0, min(1.0, float(v)))
    except Exception:
        r = (risk or "").strip().lower()
        if r == "low":
            return 0.2
        if r == "medium":
            return 0.5
        if r == "high":
            return 0.8
        return 0.5


def _resolve_weather_city(
    *,
    district: Optional[str],
    explicit_city: Optional[str],
) -> str:
    """
    - If explicit city -> use it
    - Else district -> mapped city
    - Else Colombo
    """
    if explicit_city and str(explicit_city).strip():
        return str(explicit_city).strip()

    d = (district or "").strip()
    if d:
        try:
            mapped = district_to_city(d)
            if mapped and str(mapped).strip():
                return str(mapped).strip()
        except Exception:
            pass

    return "Colombo"


def _get_rain_risk_for_date(city: str, country: str, date_str: str) -> Dict[str, Any]:
    payload = {
        "city": city,
        "country": country,
        "start_date": date_str,
        "end_date": date_str,
        "time_of_day": None,
    }
    fc = forecast_weather_logic(payload)

    monthly = fc.get("monthly") or []
    if isinstance(monthly, list) and monthly:
        rain_risk = monthly[0].get("rain_risk")
        return {
            "weather_source": fc.get("source"),
            "rain_risk": rain_risk,
            "rain_risk_0_1": _rain_risk_str_to_0_1(rain_risk),
            "weather_point": monthly[0],
            "debug": {"city_used": city, "country_used": country, "mode": "monthly"},
        }

    daily = fc.get("daily") or []
    if isinstance(daily, list) and daily:
        rain_risk = daily[0].get("rain_risk")
        return {
            "weather_source": fc.get("source"),
            "rain_risk": rain_risk,
            "rain_risk_0_1": _rain_risk_str_to_0_1(rain_risk),
            "weather_point": daily[0],
            "debug": {"city_used": city, "country_used": country, "mode": "daily"},
        }

    return {
        "weather_source": fc.get("source"),
        "rain_risk": None,
        "rain_risk_0_1": 0.5,
        "weather_point": None,
        "warning": "No daily/monthly points returned; defaulted rain risk to 0.5",
        "debug": {"city_used": city, "country_used": country, "mode": "none"},
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
# ✅ District Sustainability Score
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

        district_final = str(crowd.get("district") or district).strip()
        city_final = _resolve_weather_city(district=district_final, explicit_city=city)

        weather = _get_rain_risk_for_date(city_final, country, date)

        crowd_risk = float(crowd.get("crowd_risk_0_1", 0.5))
        rain_risk_0_1 = float(weather["rain_risk_0_1"])

        score = compute_sustainability_score(
            crowd_risk_0_1=crowd_risk,
            rain_risk_0_1=rain_risk_0_1,
            eco_preference=eco_preference,
        )

        score.setdefault("inputs", {})
        if isinstance(score.get("inputs"), dict):
            score["inputs"]["district"] = district_final
            score["inputs"]["city_used_for_weather"] = city_final

        return {
            "status": "ok",
            "district": district_final,
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

        district_final = str(crowd.get("district") or payload.district).strip()
        city_final = _resolve_weather_city(district=district_final, explicit_city=payload.city)

        weather = _get_rain_risk_for_date(city_final, payload.country or "Sri Lanka", payload.date)

        crowd_risk = float(crowd.get("crowd_risk_0_1", 0.5))
        rain_risk_0_1 = float(weather["rain_risk_0_1"])

        score = compute_sustainability_score(
            crowd_risk_0_1=crowd_risk,
            rain_risk_0_1=rain_risk_0_1,
            eco_preference=payload.eco_preference,
        )

        score.setdefault("inputs", {})
        if isinstance(score.get("inputs"), dict):
            score["inputs"]["district"] = district_final
            score["inputs"]["city_used_for_weather"] = city_final

        return {
            "status": "ok",
            "district": district_final,
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
# ✅ Attraction Sustainability Score
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

        district_from_crowd = str(crowd.get("district") or "").strip()
        city_final = _resolve_weather_city(district=district_from_crowd, explicit_city=city)

        weather = _get_rain_risk_for_date(city_final, country, date)

        crowd_risk = float(crowd.get("crowd_risk_0_1", 0.5))
        rain_risk_0_1 = float(weather["rain_risk_0_1"])

        score = compute_sustainability_score(
            crowd_risk_0_1=crowd_risk,
            rain_risk_0_1=rain_risk_0_1,
            eco_preference=eco_preference,
        )

        score.setdefault("inputs", {})
        if isinstance(score.get("inputs"), dict):
            score["inputs"]["district"] = district_from_crowd or None
            score["inputs"]["city_used_for_weather"] = city_final

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

        district_from_crowd = str(crowd.get("district") or "").strip()
        city_final = _resolve_weather_city(district=district_from_crowd, explicit_city=payload.city)

        weather = _get_rain_risk_for_date(city_final, payload.country or "Sri Lanka", payload.date)

        crowd_risk = float(crowd.get("crowd_risk_0_1", 0.5))
        rain_risk_0_1 = float(weather["rain_risk_0_1"])

        score = compute_sustainability_score(
            crowd_risk_0_1=crowd_risk,
            rain_risk_0_1=rain_risk_0_1,
            eco_preference=payload.eco_preference,
        )

        score.setdefault("inputs", {})
        if isinstance(score.get("inputs"), dict):
            score["inputs"]["district"] = district_from_crowd or None
            score["inputs"]["city_used_for_weather"] = city_final

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


# =========================
# ✅ NEW: Rank Attractions
# =========================

def _find_repo_root() -> Path:
    """
    Same pattern you used elsewhere: walk up until repo root found.
    """
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / "data").exists() and (parent / "services").exists():
            return parent
    return p.parents[5]


def _iter_attractions(obj: Any):
    # supports {"attractions":[...]} or [...], or nested dicts
    if isinstance(obj, dict) and "attractions" in obj and isinstance(obj["attractions"], list):
        for x in obj["attractions"]:
            if isinstance(x, dict):
                yield x
        return
    if isinstance(obj, list):
        for x in obj:
            if isinstance(x, dict):
                yield x
        return
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, dict):
                yield v


def _load_attractions_list() -> List[Dict[str, Any]]:
    repo_root = _find_repo_root()
    root_data = repo_root / "data" / "recommender_service"
    attractions_json = root_data / "clean/kg/attractions_clean.json"
    if not attractions_json.exists():
        raise FileNotFoundError(f"[FATAL] attractions_clean.json not found at {attractions_json.resolve()}")
    obj = json.loads(attractions_json.read_text(encoding="utf-8"))
    out: List[Dict[str, Any]] = []
    for r in _iter_attractions(obj):
        # normalize id field
        aid = r.get("attraction_id") or r.get("poi_id") or r.get("id")
        if aid:
            rr = dict(r)
            rr["attraction_id"] = str(aid)
            out.append(rr)
    return out


@router.post("/rank-attractions")
def rank_attractions(payload: RankAttractionsRequest) -> Dict[str, Any]:
    """
    Rank attractions by sustainability score for a given date.
    """
    try:
        all_atts = _load_attractions_list()

        # optional district filter
        if payload.district and str(payload.district).strip():
            d_filter = str(payload.district).strip().lower()
            all_atts = [
                a for a in all_atts
                if str(a.get("district") or "").strip().lower() == d_filter
            ]

        # avoid silly values
        limit = int(payload.limit or 10)
        if limit <= 0:
            limit = 10
        if limit > 200:
            limit = 200  # safety cap

        results: List[Dict[str, Any]] = []

        for a in all_atts:
            attraction_id = str(a.get("attraction_id") or "").strip()
            if not attraction_id:
                continue

            crowd = predict_attraction_crowd(attraction_id, payload.date)
            if crowd.get("status") != "ok":
                continue

            district_from_crowd = str(crowd.get("district") or a.get("district") or "").strip()
            city_final = _resolve_weather_city(district=district_from_crowd, explicit_city=None)

            weather = _get_rain_risk_for_date(city_final, payload.country or "Sri Lanka", payload.date)

            crowd_risk = float(crowd.get("crowd_risk_0_1", 0.5))
            rain_risk_0_1 = float(weather.get("rain_risk_0_1", 0.5))

            score = compute_sustainability_score(
                crowd_risk_0_1=crowd_risk,
                rain_risk_0_1=rain_risk_0_1,
                eco_preference=float(payload.eco_preference or 0.5),
            )

            results.append({
                "attraction_id": attraction_id,
                "title": crowd.get("attraction_title") or a.get("title") or a.get("name"),
                "district": district_from_crowd or None,
                "city_used_for_weather": city_final,
                "date": payload.date,
                "month_start": crowd.get("month_start"),
                "sustainability": score,
                "crowd": {
                    "crowd_level": crowd.get("crowd_level"),
                    "crowd_risk_0_1": crowd_risk,
                    "pressure_vs_p90": crowd.get("pressure_vs_p90"),
                    "total_district_pressure": crowd.get("total_district_pressure"),
                },
                "weather": {
                    "rain_risk": weather.get("rain_risk"),
                    "rain_risk_0_1": rain_risk_0_1,
                    "weather_source": weather.get("weather_source"),
                },
            })

        # sort best score first
        results.sort(key=lambda x: float((x.get("sustainability") or {}).get("score_0_1", 0.0)), reverse=True)

        return {
            "status": "ok",
            "date": payload.date,
            "country": payload.country,
            "eco_preference": payload.eco_preference,
            "filter_district": payload.district,
            "returned": min(limit, len(results)),
            "results": results[:limit],
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Missing artifact/file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
