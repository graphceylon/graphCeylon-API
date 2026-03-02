from __future__ import annotations
import time
from typing import Callable, Dict
from ..models import ToolCall, ToolResult, ToolErrorCode
from ..provider import ToolProvider


class LocalToolProvider(ToolProvider):
    provider_name = "local"

    def __init__(self, handlers: Dict[str, Callable[[ToolCall], dict]]):
        self.handlers = handlers

    def invoke(self, call: ToolCall) -> ToolResult:
        start = time.time()
        fn = self.handlers.get(call.name)
        if not fn:
            return ToolResult(
                ok=False,
                error=f"No local handler for tool={call.name}",
                error_code=ToolErrorCode.BAD_REQUEST,
                latency_ms=0,
                provider="local",
                tool_name=call.name,
                trace_id=call.trace_id,
            )
        try:
            data = fn(call)
            return ToolResult(
                ok=True,
                data=data if isinstance(data, dict) else {"data": data},
                latency_ms=int((time.time() - start) * 1000),
                provider="local",
                tool_name=call.name,
                trace_id=call.trace_id,
            )
        except Exception as e:
            return ToolResult(
                ok=False,
                error=str(e),
                error_code=ToolErrorCode.UNKNOWN,
                latency_ms=int((time.time() - start) * 1000),
                provider="local",
                tool_name=call.name,
                trace_id=call.trace_id,
            )