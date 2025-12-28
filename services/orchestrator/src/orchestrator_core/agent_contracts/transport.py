from __future__ import annotations

from typing import Optional, List, Literal, Dict, Any
from pydantic import Field

from .base import BaseSchema, Money, GeoPoint


TransportMode = Literal["train", "bus", "car", "tuk_tuk", "flight", "walk", "unknown"]


class TripStop(BaseSchema):
    name: str = Field(..., description="Stop/station name")
    location: Optional[GeoPoint] = Field(default=None)
    time_iso: Optional[str] = Field(default=None, description="ISO timestamp if known")


class TripLeg(BaseSchema):
    origin: str = Field(..., description="Origin place name")
    destination: str = Field(..., description="Destination place name")
    mode: TransportMode = Field(default="unknown")

    # Schedule
    departure_time_iso: Optional[str] = Field(default=None)
    arrival_time_iso: Optional[str] = Field(default=None)
    duration_minutes: Optional[int] = Field(default=None, ge=0)

    # Cost / provider
    cost: Optional[Money] = Field(default=None)
    provider: Optional[str] = Field(default=None, description="e.g., 'Sri Lanka Railways', 'CTB', 'Private'")
    service_id: Optional[str] = Field(default=None, description="Timetable trip/service id if applicable")

    stops: List[TripStop] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict, description="GTFS fields, route info, etc.")
