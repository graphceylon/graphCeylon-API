# api/schemas.py
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from ..orchestrator_core.contracts.weather import WeatherForecastResponse
from ..orchestrator_core.contracts.crowd import CrowdForecastResponse
from ..orchestrator_core.contracts.price import PriceForecastResponse
from ..orchestrator_core.contracts.itinerary import ItineraryPlanResponse
from ..orchestrator_core.contracts.itinerary_modify import ItineraryModifyResponse
from ..orchestrator_core.agent_contracts.visa_policy import VisaPolicyResponse
from ..orchestrator_core.agent_contracts.profile import PreferenceOverrides as CanonicalPreferenceOverrides
from ..orchestrator_core.agent_contracts.profile import BudgetLevel




class PreferenceOverrides(BaseModel):
    travel_style: List[str] = []           # ["nature", "culture"]
    avoid_crowds: Optional[bool] = None
    budget_level: Optional[str] = None
    eco_preference: Optional[str] = None   # "high" / "medium" / "low"
    accessibility_needs: Optional[str] = None
    food_preferences: List[str] = []
    preferred_transport: List[str] = []
    sun_sensitivity: Optional[str] = None
    rain_preference: Optional[str] = None
    temperature_preference: Optional[str] = None
    avoid_stray_animals: Optional[bool] = None
    motion_sickness: Optional[bool] = None

class Entities(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None

    poi_name: Optional[str] = None
    itinerary_id: Optional[str] = None
    current_itinerary: Optional[dict] = None
    origin_city: Optional[str] = None
    include_stops: Optional[bool] = None
    route_direction: Optional[Literal["outbound", "return", "both"]] = None
    waypoints: List[str] = Field(default_factory=list)
    stop_durations_days: Dict[str, int] = Field(default_factory=dict)

    # NEW: what *kind* of POI in the KG
    poi_category: Optional[str] = None   # "attraction", "restaurant", "hotel", ...

    # OPTIONAL: experience type if you want it later
    activity_type: Optional[str] = None  # "hiking", "surfing", etc.

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    travel_month: Optional[str] = None
    days: Optional[int] = None
    nationality_country: Optional[str] = None


    time_of_day: Optional[str] = None

    num_travelers: Optional[int] = None
    travel_with: Optional[str] = None

    origin: Optional[str] = None
    destination: Optional[str] = None

    budget_level: Optional[BudgetLevel] = None

    tags: List[str] = []

    min_star_rating: int | None = None
    max_star_rating: int | None = None  # or just exact_star_rating
    max_price_lkr: int | None = None
    currency: str | None = "LKR"
    legal_service: Optional[str] = None        # "visa" | "citizenship" | None
    citizenship_type: Optional[str] = None     


# what user sends
class OrchestrateRequest(BaseModel):
    user_id: str
    input_text: str
    channel: Optional[str] = "chat"   # later: app, web, voice
    lang: Optional[str] = "auto"      # si, ta, en, auto
    session_id: Optional[str] = None  # for multi-turn context
    entities: Optional[Dict[str, Any]] = None 
    trace_id: Optional[str] = None          # per /orchestrate call
    turn_id: Optional[str] = None           # per user message/turn
    idempotency_key: Optional[str] = None 
    context: Optional[Dict[str, Any]] = None


# what intent parser returns (after wrapping)
class ParsedIntent(BaseModel):
    domain_category: Optional[str] = None   # <--- ADD THIS LINE

    intent: str
    confidence: float
    secondary_intents: List[str] = []
    scores: Dict[str, float] = {}

    entities: Entities = Field(default_factory=Entities)
    preference_overrides: CanonicalPreferenceOverrides = Field(default_factory=CanonicalPreferenceOverrides)

    raw_text: Optional[str] = None



# each subtask in the task graph
class TaskSummary(BaseModel):
    id: str
    type: str
    status: str
    assigned_agent: Optional[str] = None


class AgentCallError(BaseModel):
    agent: str
    endpoint: str
    status_code: int
    error: str
    detail: Optional[Any] = None

class OrchestrateResponse(BaseModel):
    status: str
    message: str
    parsed_intent: ParsedIntent
    tasks: list[TaskSummary]
    protocol_mode: str

    weather_result: Optional[Any] = None
    crowd_result: Optional[CrowdForecastResponse] = None
    price_result: Optional[PriceForecastResponse] = None
    itinerary_result: Optional[ItineraryPlanResponse] = None

    modify_result: Optional[ItineraryModifyResponse] = None

    errors: List[AgentCallError] = Field(default_factory=list)

    visa_result: Optional[VisaPolicyResponse] = None
    accommodation_result: Optional[Any] = None
    pois_result: Optional[Any] = None
    transport_result: Optional[Any] = None
    attraction_result: Optional[Any] = None
    restaurant_result:Optional[Any] = None
    booking_result:Optional[Any] = None

    final_message: Optional[str] = None

    # ✅ Always a list (frontend can render safely)
    followups: List[str] = Field(default_factory=list)

    # ✅ Return a top-level trace object
    trace: Optional[Dict[str, Any]] = None

    # ✅ Optional patch (you already had this)
    session_state_patch: Optional[Dict[str, Any]] = None

    trip_id: Optional[str] = None
    agentic_meta: Optional[Dict[str, Any]] = None
    explainability: Optional[Dict[str, Any]] = None
    explainability_ui: Optional[str] = None