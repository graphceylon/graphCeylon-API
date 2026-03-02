from __future__ import annotations
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from uuid import uuid4
from enum import Enum
import time
from ...core_contract.models import EvidenceItem


"""
Single import surface for runtime/tools.

Rule:
- All tool contracts come from orchestrator_core/core_contract/models.py
- No duplicates inside runtime/
"""

from ...core_contract.models import ToolCall, ToolResult

__all__ = ["ToolCall", "ToolResult"]

class ToolErrorCode(str, Enum):
    TIMEOUT = "timeout"
    NETWORK = "network"
    BAD_REQUEST = "bad_request"
    UPSTREAM_5XX = "upstream_5xx"
    UPSTREAM_4XX = "upstream_4xx"
    CIRCUIT_OPEN = "circuit_open"
    PARSE_ERROR = "parse_error"
    UNKNOWN = "unknown"


class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any] = Field(default_factory=dict)

    # standard runtime controls
    timeout_ms: int = 20000
    retries: int = 1

    # tracing / idempotency
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str = "no_session"
    user_id: Optional[str] = None

    # write safety
    is_write: bool = False
    idempotency_key: Optional[str] = None


class ToolResult(BaseModel):
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[ToolErrorCode] = None
    latency_ms: int = 0

    provider: Optional[Literal["a2a", "mcp", "local"]] = None
    tool_name: Optional[str] = None
    trace_id: Optional[str] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)

ToolResult.model_rebuild()