from __future__ import annotations

import time
from typing import Dict, Protocol, Optional

from .models import ToolCall, ToolResult


class ToolProvider(Protocol):
    provider_name: str
    def call(self, call: ToolCall) -> ToolResult: ...


class ToolRouter:
    """
    Single entry point for tool calls.
    Guarantees:
      - always returns ToolResult
      - always sets provider, tool_name, latency_ms
      - never raises (wraps exceptions into ToolResult(ok=False))
    """

    def __init__(
        self,
        *,
        providers: Dict[str, ToolProvider],
        tool_to_provider: Dict[str, str],
        default_provider: str = "a2a",
    ) -> None:
        self.providers = providers
        self.tool_to_provider = tool_to_provider
        self.default_provider = default_provider

    def _pick_provider(self, tool_name: str) -> Optional[ToolProvider]:
        pname = self.tool_to_provider.get(tool_name, self.default_provider)
        return self.providers.get(pname)

    def call(self, call: ToolCall) -> ToolResult:
        start = time.perf_counter()

        provider = self._pick_provider(call.name)
        if provider is None:
            latency = int((time.perf_counter() - start) * 1000)
            return ToolResult(
                ok=False,
                tool_name=call.name,
                provider="unknown",
                data=None,
                error=f"No provider configured for tool '{call.name}'",
                latency_ms=latency,
                evidence=[],
            )

        try:
            res = provider.call(call)

            # provider must return ToolResult, but guard anyway
            latency = int((time.perf_counter() - start) * 1000)
            if not isinstance(res, ToolResult):
                return ToolResult(
                    ok=False,
                    tool_name=call.name,
                    provider=getattr(provider, "provider_name", "unknown"),
                    data=None,
                    error=f"Provider '{getattr(provider, 'provider_name', 'unknown')}' returned non-ToolResult",
                    latency_ms=latency,
                    evidence=[],
                )

            # enforce consistent metadata
            res.tool_name = call.name
            res.provider = getattr(provider, "provider_name", res.provider or "unknown")
            res.latency_ms = res.latency_ms or latency
            res.evidence = res.evidence or []

            return res

        except Exception as e:
            latency = int((time.perf_counter() - start) * 1000)
            return ToolResult(
                ok=False,
                tool_name=call.name,
                provider=getattr(provider, "provider_name", "unknown"),
                data=None,
                error=str(e),
                latency_ms=latency,
                evidence=[],
            )