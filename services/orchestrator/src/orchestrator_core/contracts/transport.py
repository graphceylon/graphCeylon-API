from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TransportInfoRequest(BaseModel):
    """
    Contract sent from Orchestrator -> KG service (A2A).
    """
    origin: Optional[str] = None
    destination: Optional[str] = None
    city: Optional[str] = None          # for "getting around within a city"
    country: Optional[str] = "Sri Lanka"

    time_of_day: Optional[str] = None
    days: Optional[int] = None
    budget_level: Optional[str] = None
    preferred_transport: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)

    # tracing / context
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    query: Optional[str] = None
    trace: Dict[str, Any] = Field(default_factory=dict)


class TransportOption(BaseModel):
    mode: str                           # e.g., train/bus/taxi/tuk-tuk
    summary: Optional[str] = None
    estimated_time_min: Optional[int] = None
    estimated_cost_lkr: Optional[float] = None
    tips: Optional[str] = None
    source: Optional[str] = None


class TransportInfoResponse(BaseModel):
    """
    Contract returned from KG service -> Orchestrator.
    """
    ok: bool = True
    origin: Optional[str] = None
    destination: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None

    options: List[TransportOption] = Field(default_factory=list)
    summary: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None
