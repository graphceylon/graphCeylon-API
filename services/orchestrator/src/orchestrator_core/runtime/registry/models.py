from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional


class SLA(BaseModel):
    p95_ms: Optional[int] = None
    success_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class AgentSpec(BaseModel):
    agent_id: str
    base_url: str
    protocols: List[str] = Field(default_factory=lambda: ["a2a"])
    capabilities: List[str] = Field(default_factory=list)
    sla: SLA = Field(default_factory=SLA)
    cost_weight: float = 1.0
    enabled: bool = True
