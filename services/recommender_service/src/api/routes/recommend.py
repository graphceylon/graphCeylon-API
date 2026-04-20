from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from src.itinerary.planner.itinerary_planner import recommend_city_pois_simple

router = APIRouter()

class RecommendPoisRequest(BaseModel):
    city: str
    country: Optional[str] = "Sri Lanka"
    raw_text: Optional[str] = None
    limit: Optional[int] = 20
    max_candidates: Optional[int] = 60

    model_config = {"extra": "allow"}

@router.post("/recommend/pois")
def recommend_pois(req: RecommendPoisRequest):
    try:
        return recommend_city_pois_simple(req.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))