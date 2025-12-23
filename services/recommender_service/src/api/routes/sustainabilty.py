from __future__ import annotations

from datetime import date
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.recommender_service.src.sustainability.service import forecast_poi_sustainability

router = APIRouter(prefix="/forecast", tags=["forecast"])


class SustainabilityRequest(BaseModel):
    poi_id: Optional[str] = None
    poi_name: Optional[str] = None
    month_start: Optional[date] = None
    start_date: Optional[date] = None
    total_foreign_arrivals_month: Optional[int] = None


@router.post("/sustainability")
def sustainability(req: SustainabilityRequest) -> Dict[str, Any]:
    poi_id = (req.poi_id or req.poi_name or "").strip().lower()
    if not poi_id:
        raise HTTPException(status_code=400, detail="poi_id or poi_name is required")

    if req.month_start:
        month_start = req.month_start
    elif req.start_date:
        month_start = date(req.start_date.year, req.start_date.month, 1)
    else:
        raise HTTPException(status_code=400, detail="month_start or start_date is required")

    if month_start.day != 1:
        month_start = date(month_start.year, month_start.month, 1)

    return forecast_poi_sustainability(
        poi_id=poi_id,
        month_start=month_start,
        total_foreign_arrivals_month=req.total_foreign_arrivals_month,
    )
