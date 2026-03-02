from __future__ import annotations

import time
from typing import Any, Dict

from ....core_contract.models import EvidenceItem, EvidenceSource
from ..models import ToolCall, ToolResult
from ..provider import ToolProvider

from ...registry.registry import AgentRegistry
from ...adapters.a2a import A2AHttpAdapter


class A2AToolProvider(ToolProvider):
    provider_name = "a2a"

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        adapter: A2AHttpAdapter,
        tool_endpoints: Dict[str, str],
    ) -> None:
        self.registry = registry
        self.adapter = adapter
        self.tool_endpoints = tool_endpoints  # tool_name -> endpoint path

    # ✅ ToolRouter should call .call(...) (universal)
    def call(self, call: ToolCall) -> ToolResult:
        start = time.time()

        endpoint = self.tool_endpoints.get(call.name)
        if not endpoint:
            latency_ms = int((time.time() - start) * 1000)
            return ToolResult(
                ok=False,
                tool_name=call.name,
                provider=self.provider_name,
                data=None,
                evidence=[],
                error=f"No A2A endpoint registered for tool={call.name}",
                latency_ms=latency_ms,
                meta={
                    "trace_id": call.trace_id,
                    "session_id": call.session_id,
                    "error_code": "bad_request",
                },
            )

        agent = self.registry.pick(capability=call.name, protocol="a2a")
        if not agent:
            latency_ms = int((time.time() - start) * 1000)
            return ToolResult(
                ok=False,
                tool_name=call.name,
                provider=self.provider_name,
                data=None,
                evidence=[],
                error=f"No agent found for tool={call.name}",
                latency_ms=latency_ms,
                meta={
                    "trace_id": call.trace_id,
                    "session_id": call.session_id,
                    "error_code": "unknown",
                },
            )

        # ✅ payload enrichment for tracing + idempotency (write actions)
        payload: Dict[str, Any] = dict(call.args or {})
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

            # ✅ minimal evidence item for verifier + UI drawer
            evidence = [
                EvidenceItem(
                    source=EvidenceSource.api,
                    source_id=f"a2a:{agent.agent_id}{endpoint}",
                    method="a2a_http_call",
                    snippet=f"Called {agent.agent_id}{endpoint}",
                    meta={
                        "agent_id": agent.agent_id,
                        "endpoint": endpoint,
                    },
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
                    "agent_id": agent.agent_id,
                    "endpoint": endpoint,
                },
            )

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)

            evidence = [
                EvidenceItem(
                    source=EvidenceSource.api,
                    source_id=f"a2a:{agent.agent_id}{endpoint}",
                    method="a2a_http_call",
                    snippet=f"Call failed: {agent.agent_id}{endpoint}",
                    meta={"agent_id": agent.agent_id, "endpoint": endpoint},
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
                    "agent_id": agent.agent_id,
                    "endpoint": endpoint,
                    "error_code": "network",
                },
            )