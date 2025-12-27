from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class BaseSchema(BaseModel):
    """
    Common base for all contracts.
    - extra="forbid" prevents agents from returning random keys (keeps schemas stable)
    - from_attributes=True helps if you later use ORM objects
    """
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    created_at: datetime = Field(default_factory=datetime.utcnow, description="UTC creation timestamp")
    schema_version: str = Field(default="1.0", description="Contract schema version")


class GeoPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)


class Money(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(..., ge=0.0)
    currency: str = Field(default="LKR", min_length=3, max_length=3, description="ISO currency code")


class DateRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
