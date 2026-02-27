from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from .common import BaseLocationTimeRequest


class RecommendPOIsRequest(BaseLocationTimeRequest):
    intent: str = "recommend_pois"

    tags: List[str] = []
    budget_level: Optional[str] = None
    avoid_crowds: Optional[bool] = None
    eco_preference: Optional[str] = None
    num_results: int = 5


class RecommendPOIsResponse(BaseModel):
    status: str = "ok"
    mode: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    items: List[Dict[str, Any]] = Field(default_factory=list)
