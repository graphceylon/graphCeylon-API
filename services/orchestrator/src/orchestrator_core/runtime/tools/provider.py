from __future__ import annotations
from typing import Protocol
from .models import ToolCall, ToolResult


class ToolProvider(Protocol):
    provider_name: str
    def invoke(self, call: ToolCall) -> ToolResult:
        ...