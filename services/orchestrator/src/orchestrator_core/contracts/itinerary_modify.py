from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ItineraryModifyRequest(BaseModel):
    intent: str = "modify_itinerary"

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    raw_text: str

    # ✅ Link to stored trip row (your trip_plans.trip_id)
    itinerary_id: Optional[str] = Field(default=None, description="Trip ID in orchestrator DB")

    # ✅ Provide the existing plan so the recommender can patch reliably
    current_itinerary: Optional[Dict[str, Any]] = None

    # ✅ What the user wants to change
    modification_text: str

    # Optional extracted constraints
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: Optional[int] = None

    budget_level: Optional[str] = None
    avoid_crowds: Optional[bool] = None
    travel_style: List[str] = []

    # Location context (helps modify)
    city: Optional[str] = None
    poi_name: Optional[str] = None
    country: Optional[str] = None


class ItineraryModifyResponse(BaseModel):
    status: Optional[str] = "ok"                # ✅ add status so your orchestrator ok-check works
    itinerary_id: Optional[str] = None

    # ✅ always return something (or allow None safely)
    updated_itinerary: Dict[str, Any] = {}
    summary: str = ""
    warnings: List[str] = []