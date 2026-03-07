from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator
from .common import BaseLocationTimeRequest

BudgetLevel = Literal["low", "mid", "high", "unknown"]


class ItineraryPlanRequest(BaseLocationTimeRequest):
    intent: Literal["plan_itinerary"] = "plan_itinerary"

    # core trip
    days: Optional[int] = None
    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    origin_city: Optional[str] = None

    # preference_overrides
    travel_style: List[str] = Field(default_factory=list)
    eco_preference: Optional[float] = None
    avoid_crowds: Optional[bool] = None
    food_preferences: List[str] = Field(default_factory=list)

    # constraints
    max_trip_budget_lkr: Optional[int] = None
    currency: Optional[str] = "LKR"
    budget_level: BudgetLevel = "unknown"

    # passthrough
    tags: List[str] = Field(default_factory=list)


class TravelModeUsed(BaseModel):
    type: Optional[str] = None
    origin_city: Optional[str] = None
    destination_city: Optional[str] = None
    include_stops: Optional[bool] = None
    origin_confidence: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)


class PlanItem(BaseModel):
    slot: Optional[str] = None
    kind: Optional[str] = None
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
    status: Optional[str] = None
    reason: Optional[str] = None
    question: Optional[str] = None
    options: List[str] = Field(default_factory=list)
    debug: Optional[Dict[str, Any]] = None


class ItineraryPlans(BaseModel):
    destination_plan: Optional[DestinationPlan] = None
    outbound_plan: Optional[DestinationPlan] = None
    return_plan: Optional[DestinationPlan] = None
    route_plan: Optional[RoutePlan] = None


class ItineraryMeta(BaseModel):
    destination: Optional[str] = None
    origin_city: Optional[str] = None
    days: Optional[int] = None
    start_date: Optional[str] = None


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

    # new flattened corridor outputs
    outbound_stops: List[Dict[str, Any]] = Field(default_factory=list)
    return_stops: List[Dict[str, Any]] = Field(default_factory=list)

    @staticmethod
    def _flatten_plan(plan: Optional[DestinationPlan]) -> List[Dict[str, Any]]:
        if not plan or not plan.itinerary:
            return []

        rows: List[Dict[str, Any]] = []
        for day in plan.itinerary:
            for item in day.items:
                raw = item.raw or {}
                enrichment = item.enrichment or {}
                dynamic = item.dynamic or {}

                weather = (enrichment.get("weather") or {}).get("weather_point") or {}
                sustainability = enrichment.get("sustainability") or {}

                rows.append({
                    "date": day.date,
                    "city": item.city or day.city or raw.get("city"),
                    "district": item.district or day.district or raw.get("district"),
                    "slot": item.slot,
                    "kind": item.kind,
                    "title": item.title,
                    "attraction_id": item.attraction_id,
                    "category": raw.get("category"),
                    "description": raw.get("description"),
                    "rating": raw.get("rating"),
                    "weather": {
                        "condition": weather.get("condition"),
                        "temp_c": weather.get("temp_c"),
                        "min_c": weather.get("min_c"),
                        "max_c": weather.get("max_c"),
                        "rain_risk": weather.get("rain_risk"),
                        "mean_mm": weather.get("mean_mm"),
                    } if weather else None,
                    "crowd_risk": dynamic.get("crowd_risk_0_1"),
                    "sustainability_score": sustainability.get("score_0_1"),
                    "sustainability_label": sustainability.get("label"),
                })
        return rows

    @model_validator(mode="after")
    def _fill_legacy_from_plans(self):
        dp = self.plans.destination_plan if self.plans else None
        op = self.plans.outbound_plan if self.plans else None
        rp = self.plans.return_plan if self.plans else None

        if dp:
            self.start_date = self.start_date or dp.start_date
            self.days = self.days or dp.days
            if not self.itinerary and dp.itinerary:
                self.itinerary = [d.model_dump(mode="json") for d in dp.itinerary]

        if not self.outbound_stops:
            self.outbound_stops = self._flatten_plan(op)

        if not self.return_stops:
            self.return_stops = self._flatten_plan(rp)

        return self