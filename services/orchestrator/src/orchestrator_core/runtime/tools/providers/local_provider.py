from __future__ import annotations

import time
from typing import Callable, Dict, Any

from ....core_contract.models import EvidenceItem, EvidenceSource
from ..models import ToolCall, ToolResult
from ..provider import ToolProvider


class LocalToolProvider(ToolProvider):
    provider_name = "local"

    def __init__(self, handlers: Dict[str, Callable[[ToolCall], Any]]):
        self.handlers = handlers

    # ✅ standardized entry point used by ToolRouter
    def call(self, call: ToolCall) -> ToolResult:
        start = time.time()
        fn = self.handlers.get(call.name)

        if not fn:
            latency_ms = int((time.time() - start) * 1000)
            return ToolResult(
                ok=False,
                tool_name=call.name,
                provider=self.provider_name,
                data=None,
                evidence=[],
                error=f"No local handler for tool={call.name}",
                latency_ms=latency_ms,
                meta={
                    "trace_id": call.trace_id,
                    "session_id": call.session_id,
                    "error_code": "bad_request",
                },
            )

        try:
            raw = fn(call)
            latency_ms = int((time.time() - start) * 1000)

            evidence = [
                EvidenceItem(
                    source=EvidenceSource.model,   # local logic / stub
                    source_id=f"local:{call.name}",
                    method="local_handler",
                    snippet=f"Local tool executed: {call.name}",
                    meta={},
                )
            ]

            return ToolResult(
                ok=True,
                tool_name=call.name,
                provider=self.provider_name,
                data=raw,
                evidence=evidence,
                error=None,
                latency_ms=latency_ms,
                meta={
                    "trace_id": call.trace_id,
                    "session_id": call.session_id,
                },
            )

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)

            evidence = [
                EvidenceItem(
                    source=EvidenceSource.model,
                    source_id=f"local:{call.name}",
                    method="local_handler",
                    snippet=f"Local tool failed: {call.name}",
                    meta={},
                )
            ]

            return ToolResult(
                ok=False,
                tool_name=call.name,
                provider=self.provider_name,
                data=None,
                evidence=evidence,
                error=str(e),
                latency_ms=latency_ms,
                meta={
                    "trace_id": call.trace_id,
                    "session_id": call.session_id,
                    "error_code": "unknown",
                },
            )