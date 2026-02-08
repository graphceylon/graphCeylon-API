from datetime import date, timedelta
from typing import Any, Dict, Optional, List, Union
from fastapi import APIRouter
from pydantic import BaseModel, Field
from pprint import pprint

from services.recommender_service.src.itinerary.planner.itinerary_planner import (
    build_itinerary_from_payload,
    PlannerConfig,
)
from fastapi.encoders import jsonable_encoder
import json

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


class ItineraryPlanRequest(BaseModel):
    intent: str = Field(default="plan_itinerary")
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    raw_text: Optional[str] = None

    city: Optional[str] = None
    destination: Optional[str] = None
    country: str = "Sri Lanka"
    origin_city: Optional[str] = None


    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None
    days: int = 3

    eco_preference: float = 0.5
    travel_style: Optional[List[str]] = None
    food_preferences: Optional[List[str]] = None

    max_trip_budget_lkr: Optional[int] = None
    currency: str = "LKR"


class C3RequestEnvelope(BaseModel):
    intent: str = Field(default="plan_itinerary")
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    query: Dict[str, Any] = Field(default_factory=dict)
    prefs: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    trace: Dict[str, Any] = Field(default_factory=dict)


def normalize_payload(req: Union[ItineraryPlanRequest, C3RequestEnvelope]) -> Dict[str, Any]:
    # If envelope: merge query+prefs+constraints into a single dict your planner expects
    if isinstance(req, C3RequestEnvelope):
        payload = {}
        payload.update(req.query or {})
        payload.update(req.prefs or {})
        payload.update(req.constraints or {})

        # carry identity + intent
        payload["intent"] = req.intent
        payload["user_id"] = req.user_id
        payload["session_id"] = req.session_id

        # optional: keep trace for debug (won’t hurt)
        payload["trace"] = req.trace or {}
        return payload

    # Else: flat request
    return req.model_dump()


@router.post("/plan")
def itinerary_plan(req: Union[ItineraryPlanRequest, C3RequestEnvelope]) -> Dict[str, Any]:
    try:
        payload = normalize_payload(req)

        print("\n================ C3 /itinerary/plan RECEIVED PAYLOAD ================")
        pprint(payload)
        print("====================================================================\n")

        # ✅ days: always read from payload (not hardcoded)
        days = int(payload.get("days") or 3)
        if days <= 0:
            days = 1
        payload["days"] = days

        # ✅ default start_date
        if not payload.get("start_date"):
            payload["start_date"] = date.today().isoformat()

        # ✅ default end_date (computed using days)
        if not payload.get("end_date"):
            d0 = date.fromisoformat(payload["start_date"])
            payload["end_date"] = (d0 + timedelta(days=days - 1)).isoformat()

        cfg = PlannerConfig(
            per_day_attractions=int(payload.get("per_day_attractions") or 2),
            meals_per_day=int(payload.get("meals_per_day") or 1),
            max_candidates=int(payload.get("max_candidates") or 80),
        )

        # ✅ build itinerary
        from services.recommender_service.src.itinerary.planner.itinerary_planner import (
            build_two_plans_from_payload
        )

        result = build_two_plans_from_payload(payload, cfg=cfg)


        # ✅ PRINT RESPONSE (pretty)
        print("\n================ C3 /itinerary/plan RESPONSE ================")
        # make sure it's json-serializable (handles dates, pydantic, etc.)
        safe = jsonable_encoder(result)
        print("\n================ C3 /itinerary/plan RESPONSE (TWO PLANS) ================")

        plans = safe.get("plans", {})
        for key in ["destination_plan", "route_plan"]:
            if key in plans:
                print(f"\n---------------- {key.upper()} ----------------")
                print(json.dumps(plans[key], indent=2, ensure_ascii=False))

        print("\n=============================================================\n")

        print(json.dumps(safe, indent=2, ensure_ascii=False))
        print("=============================================================\n")

        return result

    except Exception as e:
        print("\n🔥 C3 ITINERARY ERROR 🔥")
        print(type(e).__name__, str(e))
        raise