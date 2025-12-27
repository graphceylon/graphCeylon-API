from __future__ import annotations

from typing import Dict, List, Optional
from threading import Lock
from datetime import datetime

from .models import TraceEvent


class InMemoryTraceStore:
    """
    Simple in-memory trace store (good for dev + demos).
    Later you can swap this with Redis/Postgres without changing orchestrator logic.
    """
    def __init__(self, max_per_session: int = 200) -> None:
        self._lock = Lock()
        self._by_session: Dict[str, List[TraceEvent]] = {}
        self._max_per_session = max_per_session

    def add(self, ev: TraceEvent) -> None:
        with self._lock:
            arr = self._by_session.setdefault(ev.session_id, [])
            arr.append(ev)
            # keep last N
            if len(arr) > self._max_per_session:
                self._by_session[ev.session_id] = arr[-self._max_per_session :]

    def list(self, session_id: str) -> List[TraceEvent]:
        with self._lock:
            return list(self._by_session.get(session_id, []))

    def update(
        self,
        session_id: str,
        trace_id: str,
        *,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        finished_at: Optional[datetime] = None,
        latency_ms: Optional[int] = None,
        response_payload: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._lock:
            arr = self._by_session.get(session_id, [])
            for i in range(len(arr) - 1, -1, -1):
                if arr[i].trace_id == trace_id:
                    ev = arr[i].copy(deep=True)
                    if status is not None:
                        ev.status = status
                    if agent_id is not None:
                        ev.agent_id = agent_id
                    if endpoint is not None:
                        ev.endpoint = endpoint
                    if finished_at is not None:
                        ev.finished_at = finished_at
                    if latency_ms is not None:
                        ev.latency_ms = latency_ms
                    if response_payload is not None:
                        ev.response_payload = response_payload
                    if error is not None:
                        ev.error = error
                    arr[i] = ev
                    return
