from __future__ import annotations

from typing import Any, Dict, Optional

from services.recommender_service.src.sustainability.district_crowd.predict import predict_attraction_crowd
from services.recommender_service.src.sustainability.district_crowd.sustainability_score import compute_sustainability_score
from services.recommender_service.src.sustainability.risk_maps import rain_risk_to_0_1
from services.recommender_service.src.sustainability.district_city_map import district_to_city
from src.weather.logic import forecast_weather_logic


def _rain_risk_str_to_0_1(risk: Optional[str]) -> float:
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


def _resolve_weather_city(*, district: Optional[str], explicit_city: Optional[str]) -> str:
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


def enrich_attraction(
    *,
    attraction_id: str,
    date_str: str,
    eco_preference: float,
    country: str = "Sri Lanka",
    explicit_city: Optional[str] = None,
) -> Dict[str, Any]:
    # 1) crowd
    crowd = predict_attraction_crowd(attraction_id, date_str)
    print(
        f"[CROWD] attraction_id={attraction_id} date={date_str} "
        f"district={crowd.get('district')} "
        f"crowd_risk_0_1={crowd.get('crowd_risk_0_1')} "
        f"source={crowd.get('source')}"
    )

    district = str(crowd.get("district") or "").strip() or None
    city_used = _resolve_weather_city(district=district, explicit_city=explicit_city)

    # 2) weather (rain risk)
    weather = _get_rain_risk_for_date(city_used, country, date_str)

    crowd_risk = float(crowd.get("crowd_risk_0_1", 0.5))
    rain_risk_0_1 = float(weather.get("rain_risk_0_1", 0.5))

    # 3) sustainability score
    sustainability = compute_sustainability_score(
        crowd_risk_0_1=crowd_risk,
        rain_risk_0_1=rain_risk_0_1,
        eco_preference=float(eco_preference),
    )

    sustainability.setdefault("inputs", {})
    if isinstance(sustainability.get("inputs"), dict):
        sustainability["inputs"]["attraction_id"] = attraction_id
        sustainability["inputs"]["district"] = district
        sustainability["inputs"]["city_used_for_weather"] = city_used

    return {
        "attraction_id": attraction_id,
        "date": date_str,
        "city_used_for_weather": city_used,
        "crowd": crowd,
        "weather": weather,
        "sustainability": sustainability,
    }
