from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AttractionInfoRequest(BaseModel):
    """
    Contract sent from Orchestrator -> KG service (A2A)
    Keep it flexible; KG endpoint can decide what to do with fields.
    """
    city: Optional[str] = None
    country: Optional[str] = "Sri Lanka"
    poi_name: Optional[str] = None
    poi_category: Optional[str] = None
    days: Optional[int] = None
    tags: List[str] = Field(default_factory=list)

    # tracing / context (optional but useful)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    query: Optional[str] = None
    trace: Dict[str, Any] = Field(default_factory=dict)


class AttractionItem(BaseModel):
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    open_hours: Optional[str] = None
    entry_fee_lkr: Optional[float] = None
    image_url: Optional[str] = None
    source: Optional[str] = None


class AttractionInfoResponse(BaseModel):
    """
    Contract returned from KG service -> Orchestrator
    """
    ok: bool = True
    city: Optional[str] = None
    country: Optional[str] = None
    items: List[AttractionItem] = Field(default_factory=list)
    summary: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None
