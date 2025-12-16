from typing import Optional, List
from pydantic import BaseModel
from .common import BaseLocationTimeRequest


class RecommendPOIsRequest(BaseLocationTimeRequest):
    intent: str = "recommend_pois"

    tags: List[str] = []
    budget_level: Optional[str] = None
    avoid_crowds: Optional[bool] = None
    eco_preference: Optional[str] = None
    num_results: int = 5


class RecommendPOIsResponse(BaseModel):
    city: Optional[str]
    country: Optional[str]

    recommendations: List[dict]   # each dict = POI card
