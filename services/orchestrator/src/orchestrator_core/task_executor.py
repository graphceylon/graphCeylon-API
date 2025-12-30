# orchestrator_core/task_executor.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Callable, Awaitable, Any, Optional
from datetime import datetime, timezone

import anyio


@dataclass
class ExecTask:
    id: str
    type: str
    assigned_agent: str
    depends_on: List[str]


@dataclass
class ExecResult:
    id: str
    status: str
    assigned_agent: str
    started_at: str
    finished_at: str
    latency_ms: int
    output: Optional[Any] = None
    error: Optional[str] = None


# ✅ NEW: handler signature now gets (task, ctx, results_so_far)
HandlerFn = Callable[[ExecTask, Dict[str, Any], Dict[str, Any]], Awaitable[Any]]


class TaskExecutor:
    """
    Executes a DAG of tasks with dependency-aware parallel scheduling.
    Each task handler can read/write a shared ctx dict.
    """

    def __init__(self, handlers: Dict[str, HandlerFn]):
        self.handlers = handlers

    async def run(
        self,
        tasks: List[ExecTask],
        *,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> tuple[Dict[str, Any], List[ExecResult], Dict[str, Any]]:
        results: Dict[str, Any] = {}
        task_results: List[ExecResult] = []

        if ctx is None:
            ctx = {}

        remaining: Dict[str, ExecTask] = {t.id: t for t in tasks}
        completed: set[str] = set()

        async def _run_one(t: ExecTask):
            start = datetime.now(timezone.utc)
            started_at = start.isoformat()

            if t.type not in self.handlers:
                end = datetime.now(timezone.utc)
                finished_at = end.isoformat()
                task_results.append(
                    ExecResult(
                        id=t.id,
                        status="failed",
                        assigned_agent=t.assigned_agent,
                        started_at=started_at,
                        finished_at=finished_at,
                        latency_ms=int((end - start).total_seconds() * 1000),
                        output=None,
                        error=f"No handler registered for task type: {t.type}",
                    )
                )
                return

            try:
                out = await self.handlers[t.type](t, ctx, results)
                status = "completed"
                err = None
            except Exception as e:
                out = None
                status = "failed"
                err = repr(e)

            end = datetime.now(timezone.utc)
            finished_at = end.isoformat()
            latency_ms = int((end - start).total_seconds() * 1000)

            task_results.append(
                ExecResult(
                    id=t.id,
                    status=status,
                    assigned_agent=t.assigned_agent,
                    started_at=started_at,
                    finished_at=finished_at,
                    latency_ms=latency_ms,
                    output=out,
                    error=err,
                )
            )

            if status == "completed":
                results[t.id] = out

        while remaining:
            ready = [
                t for t in remaining.values()
                if all(dep in completed for dep in t.depends_on)
            ]

            if not ready:
                raise RuntimeError(f"Deadlock in task graph. Remaining: {list(remaining.keys())}")

            async with anyio.create_task_group() as tg:
                for t in ready:
                    tg.start_soon(_run_one, t)

            for t in ready:
                completed.add(t.id)
                remaining.pop(t.id, None)

        return results, task_results, ctx
