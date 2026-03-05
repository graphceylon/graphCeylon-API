from __future__ import annotations
from typing import Any, Dict, Optional, List, Literal
from pydantic import BaseModel, Field
from uuid import UUID

BookingStatus = Literal["DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED", "CONFIRMED"]

class BookingDraftCreate(BaseModel):
    user_id: UUID
    session_id: Optional[str] = None

    city: Optional[str] = None
    arrival: str
    departure: str
    adults: int = 2

    property_id: Optional[int] = None
    property_code: Optional[str] = None
    property_name: Optional[str] = None

    room_category_id: int
    room_type_id: int
    meal_plan_id: int
    rate_code_id: Optional[int] = None
    currency_id: Optional[int] = None
    currency_code: Optional[str] = None

    adult_rate: Optional[float] = None
    price_breakdown: Optional[List[Dict[str, Any]]] = None  # roomratecalculationforai.Data
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

class BookingDraftResponse(BaseModel):
    draft_id: UUID
    status: BookingStatus
    message: str

class BookingHITLRequest(BaseModel):
    draft_id: UUID
    note: Optional[str] = None

class BookingHITLApprove(BaseModel):
    draft_id: UUID
    approve: bool
    admin_id: Optional[str] = None
    reason: Optional[str] = None

class BookingConfirmRequest(BaseModel):
    draft_id: UUID