from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal
from uuid import uuid4
from enum import Enum


class ToolErrorCode(str, Enum):
    TIMEOUT = "timeout"
    NETWORK = "network"
    BAD_REQUEST = "bad_request"
    UPSTREAM_5XX = "upstream_5xx"
    UPSTREAM_4XX = "upstream_4xx"
    CIRCUIT_OPEN = "circuit_open"
    PARSE_ERROR = "parse_error"
    UNKNOWN = "unknown"


# ✅ Transport type literal — used for benchmark tagging
TransportType = Literal["a2a_http", "mcp_stdio", "mcp_streamable_http", "local", "unknown"]


class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any] = Field(default_factory=dict)

    # runtime controls
    timeout_ms: int = 20_000
    retries: int = 1

    # tracing / idempotency
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str = "no_session"
    user_id: Optional[str] = None

    # write safety
    is_write: bool = False
    idempotency_key: Optional[str] = None

    # ✅ NEW: which transport to use — router uses this to pick provider
    # If None, ToolRouter falls back to tool_to_provider mapping
    transport_type: Optional[TransportType] = None


class ToolResult(BaseModel):
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[ToolErrorCode] = None
    latency_ms: int = 0

    # ✅ provider is now the transport name for benchmark clarity
    provider: Optional[Literal["a2a", "mcp", "local"]] = None

    # ✅ NEW: exact transport used — persisted to trace_events.transport_type
    transport_type: Optional[TransportType] = None

    tool_name: Optional[str] = None
    trace_id: Optional[str] = None
    evidence: List[Any] = Field(default_factory=list)