from __future__ import annotations
from typing import Dict
from .models import ToolCall, ToolResult
from .resilience import CircuitBreaker, invoke_with_resilience
from .provider import ToolProvider


class ToolRouter:
    def __init__(self, providers: Dict[str, ToolProvider], tool_to_provider: Dict[str, str]):
        self.providers = providers                # "a2a" -> provider, "mcp" -> provider
        self.tool_to_provider = tool_to_provider  # tool_name -> provider_name
        self.breakers: Dict[str, CircuitBreaker] = {}  # per tool

    def call(self, call: ToolCall) -> ToolResult:
        p_name = self.tool_to_provider.get(call.name, "a2a")
        provider = self.providers.get(p_name)
        if not provider:
            return ToolResult(ok=False, error=f"No provider={p_name}", latency_ms=0)

        breaker = self.breakers.setdefault(call.name, CircuitBreaker())

        def _do(c: ToolCall) -> ToolResult:
            return provider.invoke(c)

        return invoke_with_resilience(call=call, breaker=breaker, do_invoke=_do)