# services/recommender_service/src/api/routes/itinerary.py
from __future__ import annotations

from typing import Any, Dict, Tuple, Optional
from fastapi import APIRouter, HTTPException

from src.poi.store import get_pois_near_city, load_pois, _resolve_anchor_from_json
from src.itinerary.ranking.enrich_and_rank import enrich_and_rank
from src.itinerary.planner.simple_planner import build_itinerary

# ✅ existing crowd predictor
from services.recommender_service.src.sustainability.district_crowd.predict import predict_district_crowd

# ✅ existing scoring + mappings
from services.recommender_service.src.sustainability.district_crowd.sustainability_score import compute_sustainability_score
from services.recommender_service.src.sustainability.risk_maps import rain_risk_to_0_1
from services.recommender_service.src.sustainability.district_city_map import district_to_city

# ✅ existing weather logic
from src.weather.logic import forecast_weather_logic

router = APIRouter(prefix="/itinerary", tags=["itinerary"])

def _poi_to_dict(p: Any) -> Dict[str, Any]:
    """
    Convert POI object -> dict safely.
    Supports:
      - dict already
      - pydantic v1/v2 models (.dict() / .model_dump())
      - dataclasses (asdict)
      - plain objects (__dict__)
    """
    if p is None:
        return {}

    if isinstance(p, dict):
        return p

    # pydantic v2
    if hasattr(p, "model_dump") and callable(getattr(p, "model_dump")):
        return p.model_dump()

    # pydantic v1
    if hasattr(p, "dict") and callable(getattr(p, "dict")):
        return p.dict()

    # dataclass
    try:
        from dataclasses import is_dataclass, asdict
        if is_dataclass(p):
            return asdict(p)
    except Exception:
        pass

    # generic python object
    if hasattr(p, "__dict__"):
        return dict(p.__dict__)

    # last resort
    return {"value": str(p)}


def _normalize_pois(items: Any) -> list[Dict[str, Any]]:
    """
    Ensure we always return List[Dict] so downstream code can do .get(...)
    """
    if items is None:
        return []
    if isinstance(items, list):
        return [_poi_to_dict(x) for x in items]
    # if store returns an iterator/tuple/set
    try:
        return [_poi_to_dict(x) for x in list(items)]
    except Exception:
        return []



def _extract_rain_label(fc: Dict[str, Any]) -> Optional[str]:
    monthly = fc.get("monthly") or []
    if isinstance(monthly, list) and monthly:
        return monthly[0].get("rain_risk")

    daily = fc.get("daily") or []
    if isinstance(daily, list) and daily:
        return daily[0].get("rain_risk")

    return None


def _weather_for_single_date(city: str, country: str, date_str: str) -> Dict[str, Any]:
    payload = {
        "city": city,
        "country": country,
        "start_date": date_str,
        "end_date": date_str,
        "time_of_day": None,
    }
    return forecast_weather_logic(payload)


def build_query_priority_prefs(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query-priority:
      - If preference_sources[key] == 'query' then we trust payload[key]
      - Otherwise we DO NOT override, but we still provide safe defaults
        so downstream ranking/scoring never crashes.
    """
    prefs_src = payload.get("preference_sources") or {}

    def is_query(k: str) -> bool:
        return str(prefs_src.get(k, "")).strip().lower() == "query"

    final_prefs: Dict[str, Any] = {}

    # Always keep core trip fields (required for itinerary)
    core_keys = [
        "city", "destination", "country",
        "start_date", "end_date", "days",
        "intent", "user_id", "session_id", "raw_text"
    ]
    for k in core_keys:
        if k in payload:
            final_prefs[k] = payload[k]

    # Only keep these if they came from query
    query_keys = [
        "eco_preference",
        "avoid_crowds",
        "rain_preference",
        "travel_style",
        "food_preferences",
        "max_trip_budget_lkr",
        "budget_level",
        "currency",
        "pace_preference",
        "cancellation_preference",
        "activity_preference",
        "adventure_level",
        "accommodation_type",
        "star_preference",
    ]
    for k in query_keys:
        if is_query(k) and k in payload:
            final_prefs[k] = payload[k]

    # Keep tags if travel_style is query-derived (optional)
    if is_query("travel_style") and "tags" in payload:
        final_prefs["tags"] = payload["tags"]

    # ✅ IMPORTANT: Provide safe defaults so enrich_and_rank() never KeyErrors
    # (these defaults do NOT violate query-priority; they only prevent crashes)
    # If the user didn't say it in query, your ranking can treat as neutral.
    if "eco_preference" not in final_prefs:
        try:
            final_prefs["eco_preference"] = float(payload.get("eco_preference", 0.5) or 0.5)
        except Exception:
            final_prefs["eco_preference"] = 0.5

    if "avoid_crowds" not in final_prefs:
        final_prefs["avoid_crowds"] = bool(payload.get("avoid_crowds", False))

    if "rain_preference" not in final_prefs:
        final_prefs["rain_preference"] = payload.get("rain_preference") or "none"

    if "food_preferences" not in final_prefs:
        final_prefs["food_preferences"] = payload.get("food_preferences") or []

    if "travel_style" not in final_prefs:
        final_prefs["travel_style"] = payload.get("travel_style") or []

    if "budget_level" not in final_prefs:
        final_prefs["budget_level"] = payload.get("budget_level") or None

    if "max_trip_budget_lkr" not in final_prefs:
        final_prefs["max_trip_budget_lkr"] = payload.get("max_trip_budget_lkr") or None

    if "currency" not in final_prefs:
        final_prefs["currency"] = payload.get("currency") or "LKR"

    return final_prefs


@router.post("/plan")
def itinerary_plan(payload: Dict[str, Any]):
    try:
        # ✅ Query-priority prefs
        final_prefs = build_query_priority_prefs(payload)

        city = final_prefs.get("city") or final_prefs.get("destination")
        start_date = final_prefs.get("start_date")
        end_date = final_prefs.get("end_date")
        days = int(final_prefs.get("days") or 3)
        country = final_prefs.get("country") or "Sri Lanka"

        # ✅ Hard validation early (return 400 instead of 500)
        if not city or not isinstance(city, str):
            raise HTTPException(status_code=400, detail="Missing required field: city (or destination).")

        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Missing required fields: start_date and/or end_date.")

        # 1) candidates from KG-clean JSON
        raw_candidates = get_pois_near_city(city)
        candidates = _normalize_pois(raw_candidates)


        # ✅ OPTIONAL: enforce vegetarian if user said it (query-priority or default)
        food_prefs = final_prefs.get("food_preferences") or []
        if isinstance(food_prefs, list) and any(
            isinstance(x, str) and x.strip().lower() == "vegetarian" for x in food_prefs
        ):
            def is_veg_restaurant(p: Dict[str, Any]) -> bool:
                tags = [t.lower() for t in (p.get("tags") or []) if isinstance(t, str)]
                cat = (p.get("category") or "").lower()
                desc = (p.get("description") or "").lower()
                title = (p.get("title") or "").lower()

                # keep non-restaurants always
                if ("restaurant" not in cat) and ("food" not in cat) and ("cafe" not in cat):
                    return True

                # restaurant must look vegetarian
                joined_tags = " ".join(tags)
                return ("veget" in joined_tags) or ("vegetarian" in desc) or ("vegetarian" in title) or ("veg" in tags)

            candidates = [c for c in candidates if is_veg_restaurant(c)]

        # 2) anchor lat/lng
        all_pois = load_pois()
        anchor_lat, anchor_lng = _resolve_anchor_from_json(all_pois, city)

        # 3) enrich + rank
        ranked = enrich_and_rank(
            candidates=candidates,
            anchor_lat=anchor_lat,
            anchor_lng=anchor_lng,
            start_date=start_date,
            end_date=end_date,
            final_prefs=final_prefs,
            city=city,
            country=country,
        )

        # 4) build itinerary schedule
        itinerary = build_itinerary(
            ranked_attractions=ranked,
            days=days,
            start_date=start_date,
            final_prefs=final_prefs,
        )

        title = f"{days}-day {', '.join(final_prefs.get('travel_style', []) or ['trip'])} to {city}".replace("  ", " ").strip()

        summary = (
            "KG-based candidate discovery → crowd pressure risk forecast → adaptive weather forecast → "
            "sustainability scoring (crowd+rain weighted by eco preference) → preference-aware ranking → "
            "simple itinerary scheduling."
        )

        return {
            "intent": "plan_itinerary",
            "user_id": final_prefs.get("user_id"),
            "session_id": final_prefs.get("session_id"),
            "city": city,
            "country": country,
            "start_date": start_date,
            "end_date": end_date,
            "days": days,

            "title": title,
            "summary": summary,

            "ranked_attractions": ranked,
            "itinerary": itinerary,

            "ranking_rule": "avoid_crowds=>crowd_risk asc" if final_prefs.get("avoid_crowds") else "blended",
            "meta": {
                "num_candidates": len(candidates),
                "num_ranked": len(ranked),
                "anchor": {"lat": anchor_lat, "lng": anchor_lng},
                "rep_date": ranked[0]["context"]["rep_date"] if ranked else None,
                "query_priority_applied": True,
                "applied_query_prefs": list(final_prefs.keys()),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        # ✅ make the error visible (so Postman doesn't just say "Internal Server Error")
        raise HTTPException(status_code=500, detail=f"itinerary/plan failed: {type(e).__name__}: {str(e)}")
