from __future__ import annotations

from typing import Generic, List, Optional, TypeVar, Literal
from pydantic import Field

from .base import BaseSchema
from .evidence import Evidence

T = TypeVar("T")


class AgentResponse(BaseSchema, Generic[T]):
    status: Literal["ok", "error"] = Field(default="ok")
    trace_id: Optional[str] = Field(default=None)

    data: Optional[T] = Field(default=None)
    evidence: List[Evidence] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    error_message: Optional[str] = Field(default=None)
    error_code: Optional[str] = Field(default=None)
