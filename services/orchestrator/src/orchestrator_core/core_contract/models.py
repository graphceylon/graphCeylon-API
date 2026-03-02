from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# -------------------------
# Evidence / Safety / Actions
# -------------------------

class EvidenceSource(str, Enum):
    kg = "kg"
    api = "api"
    curated = "curated"
    model = "model"
    cache = "cache"
    user = "user"
    unknown = "unknown"


class EvidenceItem(BaseModel):
    source: EvidenceSource = EvidenceSource.unknown
    source_id: str = ""  # e.g. "kg:restaurant:123", "api:openweather", "doc:visa_json"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    method: str = ""     # e.g. "semantic_search", "cypher_query", "http_call", "rule_filter"
    snippet: str = ""    # short text to show in UI evidence drawer
    url: Optional[str] = None
    confidence: Optional[float] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class SafetySeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class SafetyFlag(BaseModel):
    code: str
    severity: SafetySeverity = SafetySeverity.low
    message: str
    meta: Dict[str, Any] = Field(default_factory=dict)


class NextActionType(str, Enum):
    whatsapp_send = "whatsapp_send"
    calendar_create_events = "calendar_create_events"
    call_request_create = "call_request_create"
    reminder_create = "reminder_create"
    ask_followup = "ask_followup"
    booking_stub = "booking_stub"


class NextAction(BaseModel):
    action_type: NextActionType
    args: Dict[str, Any] = Field(default_factory=dict)
    requires_user_confirm: bool = True
    label: Optional[str] = None  # nice UI label
    meta: Dict[str, Any] = Field(default_factory=dict)


# -------------------------
# Tool contracts
# -------------------------

class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any] = Field(default_factory=dict)

    timeout_ms: int = 20_000
    retries: int = 0

    trace_id: str
    session_id: str
    user_id: Optional[str] = None

    is_write: bool = False
    idempotency_key: Optional[str] = None


class ToolResult(BaseModel):
    ok: bool
    tool_name: str
    provider: str = "unknown"

    data: Any = None

    evidence: List[EvidenceItem] = Field(default_factory=list)

    error: Optional[str] = None
    latency_ms: Optional[int] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


# -------------------------
# Action contracts (external world)
# -------------------------

class ActionRequest(BaseModel):
    action_type: NextActionType
    args: Dict[str, Any] = Field(default_factory=dict)

    trace_id: str
    session_id: str
    user_id: Optional[str] = None

    requires_user_confirm: bool = True
    user_confirmed: bool = False


class ActionResult(BaseModel):
    ok: bool
    action_type: NextActionType
    provider: str = "actions"
    data: Any = None
    error: Optional[str] = None
    latency_ms: Optional[int] = None
    audit_id: Optional[str] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


# -------------------------
# Agent contract (universal)
# -------------------------

class AgentResult(BaseModel):
    ok: bool

    # user-facing answer (can be empty if the agent returns only structured data)
    answer: str = ""

    # structured data payload (domain response model OR dict)
    data: Any = None

    # grounding
    evidence: List[EvidenceItem] = Field(default_factory=list)

    # planning signals
    missing_fields: List[str] = Field(default_factory=list)
    next_actions: List[NextAction] = Field(default_factory=list)

    # trust
    confidence: float = 0.5
    safety_flags: List[SafetyFlag] = Field(default_factory=list)

    # debug
    meta: Dict[str, Any] = Field(default_factory=dict)