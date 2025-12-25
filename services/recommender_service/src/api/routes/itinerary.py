# /Users/dev/Desktop/graphCeylon-API/services/recommender_service/src/api/routes/itinerary.py
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_db


router = APIRouter(prefix="/itinerary", tags=["itinerary"])


@router.post("/plan")
def itinerary_plan(payload: Dict[str, Any], db: Session = Depends(get_db)):
    """
    Temporary handler to confirm orchestrator → recommender payload correctness.
    Prints all preference-related fields and optionally a preference_sources map.
    Later you will replace this with a Pydantic request model + real logic.
    """
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

    # For now return a simple echo (so you can verify in Postman/orchestrator)
    return {
        "status": "ok",
        "message": "itinerary/plan received (debug endpoint).",
        "received_keys": sorted(list(payload.keys())),
    }
