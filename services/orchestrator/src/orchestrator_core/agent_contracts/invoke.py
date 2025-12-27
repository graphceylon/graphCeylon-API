from __future__ import annotations

from typing import Any, Dict, Optional, Literal
from pydantic import Field

from .base import BaseSchema


class AgentInvokeRequest(BaseSchema):
    trace_id: str = Field(..., description="Distributed trace id from orchestrator")
    session_id: str = Field(...)

    capability: str = Field(..., description="e.g., 'info_visa_policy', 'search_hotels', 'info_transport'")
    protocol: Literal["a2a", "mcp", "blackboard"] = Field(default="a2a")

    # Normalized entities/prefs from your entity extractor
    input: Dict[str, Any] = Field(default_factory=dict)

    user_id: Optional[str] = Field(default=None)
    lang: Optional[str] = Field(default="en")
