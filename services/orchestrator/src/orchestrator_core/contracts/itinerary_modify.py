from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class ItineraryModifyRequest(BaseModel):
    intent: str = "modify_itinerary"

    user_id: Optional[str] = None
    session_id: Optional[str] = None
    raw_text: str

    # The itinerary being modified (choose ONE approach)
    itinerary_id: Optional[str] = None                 # if stored in DB
    current_itinerary: Optional[Dict[str, Any]] = None # if passed inline

    # What user wants to change
    modification_text: str

    # Optional extracted constraints
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: Optional[int] = None

    budget_level: Optional[str] = None                 # low/medium/high
    avoid_crowds: Optional[bool] = None
    travel_style: List[str] = []

    # Optional extra signals
    city: Optional[str] = None
    poi_name: Optional[str] = None
    country: Optional[str] = None


class ItineraryModifyResponse(BaseModel):
    itinerary_id: Optional[str] = None
    updated_itinerary: Dict[str, Any]
    summary: str
    warnings: List[str] = []
