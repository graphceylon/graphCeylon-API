# /Users/dev/Desktop/graphCeylon-API/services/recommender_service/src/api/routes/itinerary.py
from __future__ import annotations

from typing import Any, Dict, Optional
from pprint import pprint


from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date, timedelta


from src.api.deps import get_db
from src.poi.store import get_pois_near_city

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


@router.post("/plan")
def itinerary_plan(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Temporary handler to confirm orchestrator → recommender payload correctness.
    Prints all preference-related fields and optionally a preference_sources map.
    Later you will replace this with a Pydantic request model + real logic.
    """
    print("\n================ FULL ITINERARY REQUEST RECEIVED =================")
    pprint(payload, width=120)
    print("=================================================================\n")
    print("\n================ RECOMMENDER /itinerary/plan RECEIVED =================")
    print(f"intent     : {payload.get('intent')}")
    print(f"user_id    : {payload.get('user_id')}")
    print(f"session_id : {payload.get('session_id')}")
    print("-----------------------------------------------------------------------")

    # Print the main preference fields you care about
    keys_to_show = [
        "travel_style",
        "food_preferences",
        "eco_preference",
        "avoid_crowds",
        "budget_level",
        "max_trip_budget_lkr",
        "currency",
        "preferred_transport",
        "walking_tolerance_minutes",
        "accommodation_type",
        "star_preference",
        "must_have_amenities",
        "cancellation_preference",
        "sun_sensitivity",
        "rain_preference",
        "temperature_preference",
        "motion_sickness",
        "tags",
    ]
    for k in keys_to_show:
        v = payload.get(k)
        if v not in (None, "", [], {}):
            print(f"{k:<24}: {v}")

    # If you later add this to payload, you'll see it here
    pref_sources: Optional[Dict[str, str]] = payload.get("preference_sources")
    if isinstance(pref_sources, dict) and pref_sources:
        print("\nPreference sources (query vs db):")
        for k, src in pref_sources.items():
            print(f"{k:<24}: {src}")

    print("=======================================================================\n")

        # -------- KG substitute: load POIs near base city --------
    base_city = payload.get("city") or payload.get("destination")

    candidates = get_pois_near_city(base_city)

    print(f"\nFound {len(candidates)} POIs near {base_city}:")
    for p in candidates:
        print(f" - {p.title} ({p.district})")


    # For now return a simple echo (so you can verify in Postman/orchestrator)
    return {
        "status": "ok",
        "message": "itinerary/plan received (debug endpoint).",
        "received_keys": sorted(list(payload.keys())),
    }
# @router.post("/plan")
# def plan_itinerary(payload: dict):
#     print("\n================ RECOMMENDER /itinerary/plan STUB HIT =================")
#     print(payload)
#     print("=======================================================================\n")

#     start = date.today()
#     days = int(payload.get("days") or 3)

#     # optional: destination comes as "destination" from your request contract
#     dest = payload.get("destination") or payload.get("city") or "Galle"

#     # Build itinerary list in your contract style: List[Dict[str, Any]]
#     # Example: [{ "day": 1, "city": "...", "items": [...] }]
#     itinerary = []
#     for i in range(days):
#         d = start + timedelta(days=i)
#         itinerary.append(
#             {
#                 "day": i + 1,
#                 "city": dest,
#                 "date": str(d),
#                 "items": [
#                     {"time": "morning", "activity": "Beach chill + swim", "place": "Unawatuna"},
#                     {"time": "afternoon", "activity": "Explore Galle Fort on a budget", "place": "Galle Fort"},
#                     {"time": "night", "activity": "Low-cost beach party spot", "place": "Unawatuna/Hikkaduwa"},
#                 ],
#             }
#         )

#     return {
#         "title": f"{days}-Day Low-Budget Beach Party Trip to {dest}",
#         "start_date": str(start),
#         "end_date": str(start + timedelta(days=days - 1)),
#         "days": days,
#         "summary": f"A minimal-budget itinerary focused on beaches + nightlife around {dest}.",
#         "itinerary": itinerary,
#         "confidence": 0.75,
#     }