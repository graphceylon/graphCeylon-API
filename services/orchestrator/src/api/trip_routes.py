from fastapi import APIRouter, Query, HTTPException
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from ..orchestrator_core.trips.trip_repo import TripRepo

router = APIRouter(prefix="/trips", tags=["Trips"])
repo = TripRepo()


@router.get("")
def list_trips(
    user_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    return repo.list_trips(user_id=user_id, limit=limit)

@router.get("/{trip_id}")
def get_trip(trip_id: str, user_id: str = Query(None)) -> Dict[str, Any]:
    trip = repo.get_trip(trip_id=trip_id, user_id=user_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    return {
        "trip_id": trip.trip_id,
        "user_id": trip.user_id,
        "title": trip.title,
        "destination": trip.destination,
        "start_date": trip.start_date,
        "travel_month": trip.travel_month,
        "days": trip.days,
        "version": trip.version,
        "plan_json": trip.plan_json,
    }
class UpdateTripPlanBody(BaseModel):
    plan_json: Dict[str, Any]
    days: Optional[int] = None

@router.patch("/{trip_id}")
def update_trip_plan(
    trip_id: str,
    body: UpdateTripPlanBody,
    user_id: str = Query(None),
) -> Dict[str, Any]:
    trip = repo.get_trip(trip_id=trip_id, user_id=user_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    repo.update_trip_plan(
        trip_id=trip_id,
        plan_json=body.plan_json,
        days=body.days,
    )

    updated = repo.get_trip(trip_id=trip_id, user_id=user_id)
    return {
        "ok": True,
        "trip_id": trip_id,
        "version": updated.version,
        "days": updated.days,
    }