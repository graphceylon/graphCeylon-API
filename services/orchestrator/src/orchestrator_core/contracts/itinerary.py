from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from .common import BaseLocationTimeRequest

BudgetLevel = Literal["low", "mid", "high", "unknown"]

class ItineraryPlanRequest(BaseLocationTimeRequest):
    intent: Literal["plan_itinerary"] = "plan_itinerary"

    # core trip
    days: Optional[int] = None
    destination: Optional[str] = None  # city/country
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    origin_city: Optional[str] = None


    # preference_overrides (directly from parsed_intent.preference_overrides)
    travel_style: List[str] = Field(default_factory=list)
    eco_preference: Optional[float] = None
    avoid_crowds: Optional[bool] = None
    food_preferences: List[str] = Field(default_factory=list)

    # constraints (trip-only)
    max_trip_budget_lkr: Optional[int] = None
    currency: Optional[str] = "LKR"
    budget_level: BudgetLevel = "unknown"

    # optional passthrough for debugging/trace
    tags: List[str] = Field(default_factory=list)



class ItineraryPlanResponse(BaseModel):
    # ✅ make optional so it won't crash if C3 doesn't return them yet
    title: Optional[str] = None
    summary: Optional[str] = None

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: Optional[int] = None

    itinerary: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: Optional[float] = None

    # ✅ optional passthrough fields if C3 returns them
    status: Optional[str] = None
    city: Optional[str] = None
    warnings: Optional[List[Any]] = None
    preferences_used: Optional[Dict[str, Any]] = None
    priorities: Optional[List[Any]] = None
