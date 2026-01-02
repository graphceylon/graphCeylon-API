from __future__ import annotations

from typing import Any, Dict, Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.recommender_service.src.itinerary.planner.itinerary_planner import (
    build_itinerary_from_payload,
    PlannerConfig,
)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date, timedelta


from src.api.deps import get_db
from src.poi.store import get_pois_near_city

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


class ItineraryPlanRequest(BaseModel):
    intent: str = Field(default="plan_itinerary")
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    raw_text: Optional[str] = None

    city: Optional[str] = None
    destination: Optional[str] = None
    country: str = "Sri Lanka"

    start_date: str  # YYYY-MM-DD
    end_date: Optional[str] = None
    days: int = 3

    eco_preference: float = 0.5
    travel_style: Optional[List[str]] = None
    food_preferences: Optional[List[str]] = None

    max_trip_budget_lkr: Optional[int] = None
    currency: str = "LKR"


@router.post("/plan")
def itinerary_plan(req: ItineraryPlanRequest) -> Dict[str, Any]:
    try:
        # you can tune defaults here
        cfg = PlannerConfig(
            per_day_attractions=2,
            meals_per_day=1,
            max_candidates=80,
        )
        return build_itinerary_from_payload(req.model_dump(), cfg=cfg)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Missing artifact/file: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    # For now return a simple echo (so you can verify in Postman/orchestrator)
    return {
        "status": "ok",
        "message": "itinerary/plan received (debug endpoint).",
        "received_keys": sorted(list(payload.keys())),
    }
# @router.post("/plan")
# def plan_itinerary(payload: dict):
#     print("\n================ RECOMMENDER /itinerary/plan STUB HIT =================")
#     print(payload)
#     print("=======================================================================\n")

#     start = date.today()
#     days = int(payload.get("days") or 3)

#     # optional: destination comes as "destination" from your request contract
#     dest = payload.get("destination") or payload.get("city") or "Galle"

#     # Build itinerary list in your contract style: List[Dict[str, Any]]
#     # Example: [{ "day": 1, "city": "...", "items": [...] }]
#     itinerary = []
#     for i in range(days):
#         d = start + timedelta(days=i)
#         itinerary.append(
#             {
#                 "day": i + 1,
#                 "city": dest,
#                 "date": str(d),
#                 "items": [
#                     {"time": "morning", "activity": "Beach chill + swim", "place": "Unawatuna"},
#                     {"time": "afternoon", "activity": "Explore Galle Fort on a budget", "place": "Galle Fort"},
#                     {"time": "night", "activity": "Low-cost beach party spot", "place": "Unawatuna/Hikkaduwa"},
#                 ],
#             }
#         )

#     return {
#         "title": f"{days}-Day Low-Budget Beach Party Trip to {dest}",
#         "start_date": str(start),
#         "end_date": str(start + timedelta(days=days - 1)),
#         "days": days,
#         "summary": f"A minimal-budget itinerary focused on beaches + nightlife around {dest}.",
#         "itinerary": itinerary,
#         "confidence": 0.75,
#     }
