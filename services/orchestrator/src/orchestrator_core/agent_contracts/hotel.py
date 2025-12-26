from __future__ import annotations

from typing import Optional, List, Literal, Dict, Any
from pydantic import Field

from .base import BaseSchema, Money, GeoPoint, DateRange


class CancellationPolicy(BaseSchema):
    policy_type: Literal["free_cancellation", "non_refundable", "partial_refund", "unknown"] = Field(default="unknown")
    description: Optional[str] = Field(default=None)
    deadline_iso: Optional[str] = Field(default=None, description="ISO timestamp deadline if applicable")


class Offer(BaseSchema):
    hotel_id: Optional[str] = Field(default=None)
    hotel_name: str = Field(...)

    city: Optional[str] = Field(default=None)
    region: Optional[str] = Field(default=None)
    location: Optional[GeoPoint] = Field(default=None)

    rating: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    star_rating: Optional[int] = Field(default=None, ge=1, le=5)

    price_total: Optional[Money] = Field(default=None, description="Total price for stay if known")
    price_per_night: Optional[Money] = Field(default=None)
    date_range: Optional[DateRange] = Field(default=None)

    room_type: Optional[str] = Field(default=None)
    meal_plan: Optional[str] = Field(default=None, description="e.g., 'Breakfast included'")
    cancellation: Optional[CancellationPolicy] = Field(default=None)

    amenities: List[str] = Field(default_factory=list)
    booking_url: Optional[str] = Field(default=None)

    meta: Dict[str, Any] = Field(default_factory=dict)
