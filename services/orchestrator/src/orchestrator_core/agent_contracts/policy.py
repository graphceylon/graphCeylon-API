from __future__ import annotations

from typing import Optional, List, Literal
from pydantic import Field

from .base import BaseSchema, DateRange, Money


VisaRequirementType = Literal[
    "visa_free",
    "eta_required",
    "visa_on_arrival",
    "embassy_visa",
    "unknown",
]


class PolicyRestriction(BaseSchema):
    code: str = Field(..., description="Restriction code, e.g., 'PERMIT_REQUIRED', 'CLOSED_DAY'")
    message: str = Field(..., description="Human-readable restriction")
    applies_to: Optional[str] = Field(default=None, description="What it applies to (poi, activity, region)")
    severity: Literal["info", "warning", "blocker"] = Field(default="warning")


class PolicyRule(BaseSchema):
    nationality: str = Field(..., description="Nationality / country code or name")
    requirement_type: VisaRequirementType = Field(default="unknown")

    visa_name: Optional[str] = Field(default=None, description="e.g., 'ETA', 'Tourist Visa'")
    max_stay_days: Optional[int] = Field(default=None, ge=1)
    processing_time_days: Optional[int] = Field(default=None, ge=0)

    fee: Optional[Money] = Field(default=None)
    validity: Optional[DateRange] = Field(default=None, description="Validity window if applicable")

    notes: Optional[str] = Field(default=None, description="Additional notes or conditions")
    restrictions: List[PolicyRestriction] = Field(default_factory=list)
