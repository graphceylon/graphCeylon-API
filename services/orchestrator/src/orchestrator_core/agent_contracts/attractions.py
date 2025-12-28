from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import Field

from .base import BaseSchema, GeoPoint


class OpenHours(BaseSchema):
    opens: Optional[str] = Field(default=None, description="HH:MM")
    closes: Optional[str] = Field(default=None, description="HH:MM")
    closed_days: List[str] = Field(default_factory=list, description="e.g., ['Tuesday']")


class AttractionRec(BaseSchema):
    poi_id: Optional[str] = Field(default=None)
    name: str = Field(...)

    city: Optional[str] = Field(default=None)
    region: Optional[str] = Field(default=None)
    location: Optional[GeoPoint] = Field(default=None)

    tags: List[str] = Field(default_factory=list, description="e.g., ['nature','culture']")
    recommended_duration_minutes: Optional[int] = Field(default=None, ge=0)

    open_hours: Optional[OpenHours] = Field(default=None)
    ticket_required: Optional[bool] = Field(default=None)
    permit_required: Optional[bool] = Field(default=None)

    summary: Optional[str] = Field(default=None, description="Short description for the user")
    meta: Dict[str, Any] = Field(default_factory=dict)
