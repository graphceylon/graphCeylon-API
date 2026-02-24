from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class ModifyOp(BaseModel):
    op: str
    # keep it flexible for v1
    day: Optional[int] = None
    day_a: Optional[int] = None
    day_b: Optional[int] = None
    days: Optional[int] = None
    start_date: Optional[str] = None
    delta: Optional[int] = None
    ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    count: Optional[int] = None
    slot: Optional[str] = None
    to_day: Optional[int] = None
    to_slot: Optional[str] = None
    query: Optional[str] = None
    patch: Optional[Dict[str, Any]] = None
    preserve: Optional[List[str]] = None
    preserve_rules: Optional[Dict[str, Any]] = None

class ChangeRequest(BaseModel):
    ops: List[ModifyOp] = Field(default_factory=list)
    notes: str = ""
    strict: bool = False

class ItineraryModifyRequest(BaseModel):
    trip_id: str
    existing_plan: Dict[str, Any]
    change_request: ChangeRequest
    context: Dict[str, Any] = Field(default_factory=dict)

class ItineraryModifyResponse(BaseModel):
    status: str
    trip_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    plan: Optional[Dict[str, Any]] = None
    diff: Optional[Dict[str, Any]] = None