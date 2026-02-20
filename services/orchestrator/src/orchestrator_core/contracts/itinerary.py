from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from .common import BaseLocationTimeRequest
from pydantic import BaseModel, Field, model_validator



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



# ---------- NEW: nested models for plans ----------
class TravelModeUsed(BaseModel):
    type: Optional[str] = None  # "city" | "corridor" | ...
    origin_city: Optional[str] = None
    destination_city: Optional[str] = None
    include_stops: Optional[bool] = None
    origin_confidence: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)

class PlanItem(BaseModel):
    slot: Optional[str] = None               # morning/afternoon/evening
    kind: Optional[str] = None               # attraction/hotel/transport
    attraction_id: Optional[str] = None
    title: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None

    rank_score_base: Optional[float] = None
    rank_score_final: Optional[float] = None

    dynamic: Optional[Dict[str, Any]] = None
    enrichment: Optional[Dict[str, Any]] = None
    raw: Optional[Dict[str, Any]] = None

class PlanDay(BaseModel):
    date: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    items: List[PlanItem] = Field(default_factory=list)

class DestinationPlan(BaseModel):
    status: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    start_date: Optional[str] = None
    days: Optional[int] = None

    travel_mode_used: Optional[TravelModeUsed] = None
    priorities: List[Any] = Field(default_factory=list)
    preferences_used: Optional[Dict[str, Any]] = None
    warnings: List[Any] = Field(default_factory=list)

    itinerary: List[PlanDay] = Field(default_factory=list)
    debug: Optional[Dict[str, Any]] = None

class RoutePlan(BaseModel):
    status: Optional[str] = None                  # "needs_clarification" etc.
    reason: Optional[str] = None
    question: Optional[str] = None
    options: List[str] = Field(default_factory=list)
    debug: Optional[Dict[str, Any]] = None

class ItineraryPlans(BaseModel):
    destination_plan: Optional[DestinationPlan] = None
    route_plan: Optional[RoutePlan] = None
    # later you can add: scenic_plan, budget_plan, luxury_plan, etc.

class ItineraryMeta(BaseModel):
    destination: Optional[str] = None
    origin_city: Optional[str] = None
    days: Optional[int] = None
    start_date: Optional[str] = None

# ---------- UPDATED RESPONSE ----------
class ItineraryPlanResponse(BaseModel):
    status: Optional[str] = None
    meta: Optional[ItineraryMeta] = None
    plans: Optional[ItineraryPlans] = None

    # legacy
    title: Optional[str] = None
    summary: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: Optional[int] = None
    itinerary: List[Dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _fill_legacy_from_destination_plan(self):
        dp = self.plans.destination_plan if self.plans else None
        if dp:
            self.start_date = self.start_date or dp.start_date
            self.days = self.days or dp.days
            # If you want: flatten the rich itinerary into raw dicts
            if not self.itinerary and dp.itinerary:
                self.itinerary = [d.model_dump(mode="json") for d in dp.itinerary]
        return self