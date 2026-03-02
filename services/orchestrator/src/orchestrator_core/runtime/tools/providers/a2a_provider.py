from __future__ import annotations
import time
from typing import Dict, Any, Optional

from ..models import ToolCall, ToolResult, ToolErrorCode
from ..provider import ToolProvider

# reuse your existing objects
from ...registry.registry import AgentRegistry
from ...adapters.a2a import A2AHttpAdapter

class A2AToolProvider(ToolProvider):
    provider_name = "a2a"

    def __init__(self, *, registry: AgentRegistry, adapter: A2AHttpAdapter, tool_endpoints: Dict[str, str]):
        self.registry = registry
        self.adapter = adapter
        self.tool_endpoints = tool_endpoints  # tool_name -> endpoint path

    def invoke(self, call: ToolCall) -> ToolResult:
        start = time.time()
        endpoint = self.tool_endpoints.get(call.name)
        if not endpoint:
            return ToolResult(
                ok=False,
                error=f"No A2A endpoint registered for tool={call.name}",
                error_code=ToolErrorCode.BAD_REQUEST,
                latency_ms=0,
                provider="a2a",
                tool_name=call.name,
                trace_id=call.trace_id,
            )

        agent = self.registry.pick(capability=call.name, protocol="a2a")
        if not agent:
            return ToolResult(
                ok=False,
                error=f"No agent found for tool={call.name}",
                error_code=ToolErrorCode.UNKNOWN,
                latency_ms=0,
                provider="a2a",
                tool_name=call.name,
                trace_id=call.trace_id,
            )

        # idempotency headers (write actions)
        payload = dict(call.args or {})
        payload["trace_id"] = call.trace_id
        payload["session_id"] = call.session_id
        if call.user_id:
            payload["user_id"] = call.user_id
        if call.is_write and call.idempotency_key:
            payload["idempotency_key"] = call.idempotency_key

        try:
            raw = self.adapter.invoke(
                base_url=agent.base_url,
                endpoint=endpoint,
                payload=payload,
                timeout=int(call.timeout_ms / 1000),
            )
            latency_ms = int((time.time() - start) * 1000)
            return ToolResult(
                ok=True,
                data=raw if isinstance(raw, dict) else {"raw": raw},
                latency_ms=latency_ms,
                provider="a2a",
                tool_name=call.name,
                trace_id=call.trace_id,
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            return ToolResult(
                ok=False,
                error=str(e),
                error_code=ToolErrorCode.NETWORK,
                latency_ms=latency_ms,
                provider="a2a",
                tool_name=call.name,
                trace_id=call.trace_id,
            )