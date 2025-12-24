from __future__ import annotations

from datetime import date
from typing import Dict, Optional, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.crowd.data.arrivals_resolver import resolve_total_foreign_arrivals_month
from src.crowd.inference.crowd_model import forecast_poi_crowd

router = APIRouter(prefix="/forecast", tags=["forecast"])


class CrowdForecastRequest(BaseModel):
    # orchestrator-style fields
    poi_name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    # direct mode fields
    poi_id: Optional[str] = None
    month_start: Optional[date] = None
    total_foreign_arrivals_month: Optional[int] = None

    telecom_district_counts: Optional[Dict[str, float]] = None
    region_priors: Optional[Dict[str, float]] = None
    poi_priors: Optional[Dict[str, Dict[str, float]]] = None

    prior_strength_region: float = 60.0
    prior_strength_poi: float = 50.0
    evidence_strength_telecom: float = 220.0


@router.post("/crowd")
def crowd_forecast(req: CrowdForecastRequest) -> Dict[str, Any]:
    poi_id = (req.poi_id or req.poi_name or "").strip().lower()
    if not poi_id:
        raise HTTPException(status_code=400, detail="poi_id or poi_name is required")

    # month_start
    if req.month_start:
        month_start = req.month_start
    elif req.start_date:
        month_start = date(req.start_date.year, req.start_date.month, 1)
    else:
        raise HTTPException(status_code=400, detail="month_start or start_date is required")

    if month_start.day != 1:
        month_start = date(month_start.year, month_start.month, 1)

    # arrivals
    if req.total_foreign_arrivals_month is not None:
        arrivals = int(req.total_foreign_arrivals_month)
        arrivals_source = "override"
    else:
        res = resolve_total_foreign_arrivals_month(month_start)
        arrivals = res.arrivals
        arrivals_source = res.source

    out = forecast_poi_crowd(
        poi_id=poi_id,
        month_start=month_start,
        total_foreign_arrivals_month=arrivals,
        telecom_district_counts=req.telecom_district_counts,
        region_priors=req.region_priors,
        poi_priors=req.poi_priors,
        prior_strength_region=req.prior_strength_region,
        prior_strength_poi=req.prior_strength_poi,
        evidence_strength_telecom=req.evidence_strength_telecom,
    )

    out["arrivals_source"] = arrivals_source
    return out
