# api/schemas.py
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from ..orchestrator_core.contracts.weather import WeatherForecastResponse

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

    # NEW: what *kind* of POI in the KG
    poi_category: Optional[str] = None   # "attraction", "restaurant", "hotel", ...

    # OPTIONAL: experience type if you want it later
    activity_type: Optional[str] = None  # "hiking", "surfing", etc.

    start_date: Optional[str] = None
    end_date: Optional[str] = None
    travel_month: Optional[str] = None
    days: Optional[int] = None

    time_of_day: Optional[str] = None

    num_travelers: Optional[int] = None
    travel_with: Optional[str] = None

    origin: Optional[str] = None
    destination: Optional[str] = None

    budget_level: Optional[str] = None

    tags: List[str] = []

    min_star_rating: int | None = None
    max_star_rating: int | None = None  # or just exact_star_rating
    max_price_lkr: int | None = None
    currency: str | None = "LKR"


# what user sends
class OrchestrateRequest(BaseModel):
    user_id: str
    input_text: str
    channel: Optional[str] = "chat"   # later: app, web, voice
    lang: Optional[str] = "auto"      # si, ta, en, auto
    session_id: Optional[str] = None  # for multi-turn context


# what intent parser returns (after wrapping)
class ParsedIntent(BaseModel):
    domain_category: Optional[str] = None   # <--- ADD THIS LINE

    intent: str
    confidence: float
    secondary_intents: List[str] = []
    scores: Dict[str, float] = {}

    entities: Entities = Field(default_factory=Entities)
    preference_overrides: PreferenceOverrides = Field(default_factory=PreferenceOverrides)

    raw_text: Optional[str] = None



# each subtask in the task graph
class TaskSummary(BaseModel):
    id: str
    type: str
    status: str
    assigned_agent: Optional[str] = None


class OrchestrateResponse(BaseModel):
    status: str
    message: str
    parsed_intent: ParsedIntent
    tasks: list[TaskSummary]
    protocol_mode: str
    weather_result: Optional[WeatherForecastResponse] = None




