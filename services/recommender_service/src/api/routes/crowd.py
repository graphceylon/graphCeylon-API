from __future__ import annotations

from datetime import date
from typing import Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.crowd.inference.crowd_model import forecast_poi_crowd

router = APIRouter(prefix="/forecast", tags=["forecast"])


class CrowdForecastRequest(BaseModel):
    poi_id: str = Field(..., examples=["sigiriya"])
    month_start: date = Field(..., examples=["2026-01-01"])

    # If you don't have SARIMA ready, you can also use SLTDA historical month value
    total_foreign_arrivals_month: int = Field(..., ge=0, examples=[280000])

    # optional overrides
    telecom_district_counts: Dict[str, float] = Field(default_factory=dict)
    region_priors: Dict[str, float] = Field(default_factory=dict)
    poi_priors: Dict[str, Dict[str, float]] = Field(default_factory=dict)

    # optional sensitivity override
    prior_strength_region: float = 60.0
    prior_strength_poi: float = 50.0
    evidence_strength_telecom: float = 220.0


@router.post("/crowd")
def crowd_forecast(req: CrowdForecastRequest):
    if req.month_start.day != 1:
        raise HTTPException(status_code=400, detail="month_start must be the first day of the month (YYYY-MM-01).")

    return forecast_poi_crowd(
        poi_id=req.poi_id.strip().lower(),
        month_start=req.month_start,
        total_foreign_arrivals_month=req.total_foreign_arrivals_month,
        telecom_district_counts=req.telecom_district_counts or None,
        region_priors=req.region_priors or None,
        poi_priors=req.poi_priors or None,
        prior_strength_region=req.prior_strength_region,
        prior_strength_poi=req.prior_strength_poi,
        evidence_strength_telecom=req.evidence_strength_telecom,
    )
