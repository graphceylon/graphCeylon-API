from __future__ import annotations
import time
from typing import Dict, Any, Optional
from ..models import ToolCall, ToolResult, ToolErrorCode
from ..provider import ToolProvider


class MCPToolProvider(ToolProvider):
    provider_name = "mcp"

    def __init__(self, client):
        """
        client must expose: client.call_tool(name: str, args: dict, timeout_ms: int) -> dict
        You can implement this client later using whichever MCP library/transport you chose.
        """
        self.client = client

    def invoke(self, call: ToolCall) -> ToolResult:
        start = time.time()
        try:
            raw = self.client.call_tool(call.name, call.args, timeout_ms=call.timeout_ms)
            return ToolResult(
                ok=True,
                data=raw if isinstance(raw, dict) else {"raw": raw},
                latency_ms=int((time.time() - start) * 1000),
                provider="mcp",
                tool_name=call.name,
                trace_id=call.trace_id,
            )
        except Exception as e:
            return ToolResult(
                ok=False,
                error=str(e),
                error_code=ToolErrorCode.NETWORK,
                latency_ms=int((time.time() - start) * 1000),
                provider="mcp",
                tool_name=call.name,
                trace_id=call.trace_id,
            )