from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Callable
from .models import ToolCall, ToolResult, ToolErrorCode


@dataclass
class CircuitBreaker:
    fail_threshold: int = 5
    reset_after_sec: int = 20

    failures: int = 0
    opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if (time.time() - self.opened_at) >= self.reset_after_sec:
            # half-open reset
            self.failures = 0
            self.opened_at = None
            return True
        return False

    def record_success(self):
        self.failures = 0
        self.opened_at = None

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.fail_threshold:
            self.opened_at = time.time()


def invoke_with_resilience(
    *,
    call: ToolCall,
    breaker: CircuitBreaker,
    do_invoke: Callable[[ToolCall], ToolResult],
) -> ToolResult:
    if not breaker.allow():
        return ToolResult(
            ok=False,
            error="Circuit open (tool temporarily disabled)",
            error_code=ToolErrorCode.CIRCUIT_OPEN,
            latency_ms=0,
            provider=None,
            tool_name=call.name,
            trace_id=call.trace_id,
        )

    # retries
    last: ToolResult | None = None
    for attempt in range(call.retries + 1):
        out = do_invoke(call)
        last = out
        if out.ok:
            breaker.record_success()
            return out
    breaker.record_failure()
    return last or ToolResult(ok=False, error="Unknown failure", error_code=ToolErrorCode.UNKNOWN)