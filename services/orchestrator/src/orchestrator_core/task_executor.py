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


class TaskExecutor:
    """
    Executes a DAG of tasks with dependency-aware parallel scheduling.
    """

    def __init__(self, handlers: Dict[str, Callable[[], Awaitable[Any]]]):
        """
        handlers: maps task.type -> async callable that runs that task
        """
        self.handlers = handlers

    async def run(self, tasks: List[ExecTask]) -> tuple[Dict[str, Any], List[ExecResult]]:
        results: Dict[str, Any] = {}
        task_results: List[ExecResult] = []

        remaining: Dict[str, ExecTask] = {t.id: t for t in tasks}
        completed: set[str] = set()

        async def _run_one(t: ExecTask):
            start = datetime.now(timezone.utc)
            started_at = start.isoformat()

            try:
                fn = self.handlers[t.type]
            except KeyError:
                end = datetime.now(timezone.utc)
                raise RuntimeError(f"No handler registered for task type: {t.type}") from None

            try:
                out = await fn()
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
            # ready tasks = all deps satisfied
            ready = [
                t for t in remaining.values()
                if all(dep in completed for dep in t.depends_on)
            ]

            if not ready:
                # circular dependency or waiting on failed tasks that are required
                raise RuntimeError(f"Deadlock in task graph. Remaining: {list(remaining.keys())}")

            # Run all ready tasks in parallel
            async with anyio.create_task_group() as tg:
                for t in ready:
                    tg.start_soon(_run_one, t)

            # Move finished tasks to completed set
            for t in ready:
                completed.add(t.id)
                remaining.pop(t.id, None)

        return results, task_results
