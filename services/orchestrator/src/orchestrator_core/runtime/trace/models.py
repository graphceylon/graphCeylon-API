from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class TraceEvent(BaseModel):
    trace_id: str
    session_id: str
    user_id: Optional[str] = None

    task_id: str
    capability: str
    protocol: str
    agent_id: Optional[str] = None
    endpoint: Optional[str] = None

    status: str = Field(default="started")  # started|ok|error
    started_at: datetime
    finished_at: Optional[datetime] = None
    latency_ms: Optional[int] = None

    request_payload: Optional[Dict[str, Any]] = None
    response_payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
