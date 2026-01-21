from __future__ import annotations
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class C3RequestEnvelope(BaseModel):
    intent: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    query: Dict[str, Any] = Field(default_factory=dict)
    prefs: Dict[str, Any] = Field(default_factory=dict)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    trace: Dict[str, Any] = Field(default_factory=dict)
