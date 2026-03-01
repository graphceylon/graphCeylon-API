from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TraceEvent:
    trace_id: str
    session_id: str
    user_id: Optional[str]
    task_id: Optional[str]
    capability: Optional[str]
    protocol: Optional[str]
    agent_id: Optional[str]
    endpoint: Optional[str]
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    latency_ms: Optional[int] = None
    request_payload: Optional[Dict[str, Any]] = None
    response_payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class InMemoryTraceStore:
    def __init__(self, max_per_session: int = 500):
        self.max_per_session = max_per_session
        self._store: Dict[str, List[TraceEvent]] = {}

    def add(self, event: TraceEvent):
        session_id = event.session_id
        if session_id not in self._store:
            self._store[session_id] = []

        self._store[session_id].append(event)

        # enforce limit
        if len(self._store[session_id]) > self.max_per_session:
            self._store[session_id] = self._store[session_id][-self.max_per_session:]

    def update(self, session_id: str, trace_id: str, **updates):
        events = self._store.get(session_id, [])
        for e in events:
            if e.trace_id == trace_id:
                for k, v in updates.items():
                    setattr(e, k, v)
                break

    def get_session(self, session_id: str) -> List[TraceEvent]:
        return self._store.get(session_id, [])