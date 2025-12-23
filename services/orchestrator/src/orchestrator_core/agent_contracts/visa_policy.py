from __future__ import annotations

from enum import Enum
from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# If you already have BaseServiceRequest in .common, keep using it.
# Otherwise, make this inherit BaseModel directly.
try:
    from .common import BaseServiceRequest  # your existing base
except Exception:
    BaseServiceRequest = BaseModel  # fallback




class VisaPurpose(str, Enum):
    tourism = "tourism"
    business = "business"
    transit = "transit"
    other = "other"
    dual_citizenship = "dual_citizenship"  # ✅ add this



class PassportType(str, Enum):
    ordinary = "ordinary"
    diplomatic = "diplomatic"
    official = "official"
    other = "other"


class EntryType(str, Enum):
    single = "single"
    double = "double"
    multiple = "multiple"


class VisaAskType(str, Enum):
    eligibility = "eligibility"
    requirements = "requirements"
    fees = "fees"
    extension = "extension"
    processing_time = "processing_time"
    validity = "validity"
    where_to_apply = "where_to_apply"
    other = "other"


class TravelWindow(BaseModel):
    start_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")


class VisaPolicyRequest(BaseServiceRequest):
    """
    Canonical request the orchestrator sends to your friend's KG interface layer.
    This is the thing THEY convert into Cypher.
    """
    intent: str = "info_visa_policy"

    # identity / tracing
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    raw_text: str = ""

    # core entities
    nationality_country: Optional[str] = None
    destination_country: Optional[str] = "Sri Lanka"

    intended_stay_days: Optional[int] = None
    travel_window: Optional[TravelWindow] = None

    # broad coverage (optional)
    purpose: Optional[VisaPurpose] = None
    passport_type: Optional[PassportType] = PassportType.ordinary
    entry_type: Optional[EntryType] = None
    prior_visa_or_eta: Optional[bool] = None
    ask_type: Optional[VisaAskType] = None

    # extra flexible bucket
    extra: Dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source: str
    url: Optional[str] = None
    node_id: Optional[str] = None
    quote: Optional[str] = None
    retrieved_at: Optional[str] = None


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rule_type: str
    title: str
    details: str
    conditions: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[Evidence] = Field(default_factory=list)


class VisaPolicyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: Literal["ok", "no_result", "needs_clarification", "error"] = "ok"

    destination_country: str = "Sri Lanka"
    nationality_country: Optional[str] = None

    purpose: Optional[str] = None
    passport_type: Optional[str] = None
    entry_type: Optional[str] = None

    travel_window: Optional[TravelWindow] = None
    intended_stay_days: Optional[int] = None

    summary: str = ""
    rules: List[PolicyRule] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
