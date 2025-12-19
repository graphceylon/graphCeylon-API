from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from .common import BaseLocationTimeRequest


class ItineraryPlanRequest(BaseLocationTimeRequest):
    intent: str = "plan_itinerary"

    # trip specifics
    days: Optional[int] = None
    origin: Optional[str] = None
    destination: Optional[str] = None  # could be country/city; keep flexible

    # preferences (simple for now)
    travel_style: List[str] = []
    budget_level: Optional[str] = None          # low|medium|high
    avoid_crowds: Optional[bool] = None


class ItineraryPlanResponse(BaseModel):
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: Optional[int] = None

    summary: str
    itinerary: List[Dict[str, Any]] = []   # e.g. [{day, city, items:[...]}]
    confidence: Optional[float] = None
