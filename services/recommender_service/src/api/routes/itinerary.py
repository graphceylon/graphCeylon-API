# services/recommender_service/src/api/routes/itinerary.py
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter

from src.poi.store import get_pois_near_city, load_pois, _resolve_anchor_from_json
from src.itinerary.ranking.enrich_and_rank import enrich_and_rank
from src.itinerary.planner.simple_planner import build_itinerary  # <-- adjust path to your planner file

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


@router.post("/plan")
def itinerary_plan(payload: Dict[str, Any]):
    city = payload.get("city") or payload.get("destination")
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    days = int(payload.get("days") or 3)

    # prefs for ranking/planner
    final_prefs = payload  # (MVP: payload already contains merged prefs)

    # 1) candidates from KG-clean JSON
    candidates = get_pois_near_city(city)

    # 2) anchor lat/lng (reuse same resolver for meta + distance calculations)
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
        country=payload.get("country") or "Sri Lanka",
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
        },
    }
