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
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: Optional[int] = None

    summary: str
    itinerary: List[Dict[str, Any]] = []   # e.g. [{day, city, items:[...]}]
    confidence: Optional[float] = None
