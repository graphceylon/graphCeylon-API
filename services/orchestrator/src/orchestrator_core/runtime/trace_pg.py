from __future__ import annotations
import json, hashlib
from dataclasses import asdict
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone


import psycopg
from psycopg.types.json import Json

def sha256_json(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class PostgresTraceStore:
    def __init__(self, dsn: str):
        self.dsn = dsn

    # ---- RUNS ----
    def start_run(
        self,
        *,
        trace_id: str,
        user_id: Optional[str],
        session_id: str,
        turn_id: Optional[str],
        request_payload: Dict[str, Any],
    ) -> None:
        sql = """
        INSERT INTO trace_runs(trace_id, user_id, session_id, turn_id, request_payload, status)
        VALUES (%s,%s,%s,%s,%s,'started')
        ON CONFLICT (trace_id) DO UPDATE
        SET request_payload = EXCLUDED.request_payload
        """
        with psycopg.connect(self.dsn) as conn:
            with psycopg.connect(self.dsn) as conn:
                conn.execute(sql, (trace_id, user_id, session_id, turn_id, Json(request_payload)))
                conn.commit()

    def update_run(
        self,
        *,
        trace_id: str,
        parsed_intent: Optional[Dict[str, Any]] = None,
        planned_tasks: Optional[Dict[str, Any]] = None,
        final_response: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
    ) -> None:
        parts = []
        params = []
        if parsed_intent is not None:
            parts.append("parsed_intent=%s")
            params.append(Json(parsed_intent))

        if planned_tasks is not None:
            parts.append("planned_tasks=%s")
            params.append(Json(planned_tasks))

        if final_response is not None:
            parts.append("final_response=%s")
            params.append(Json(final_response))

        if not parts:
            return

        sql = f"UPDATE trace_runs SET {', '.join(parts)} WHERE trace_id=%s"
        params.append(trace_id)

        with psycopg.connect(self.dsn) as conn:
            conn.execute(sql, tuple(params))
            conn.commit()

    # ---- EVENTS ----
    def add_event(
        self,
        *,
        trace_id: str,
        session_id: str,
        user_id: Optional[str],
        turn_id: Optional[str],
        event_type: str,
        status: Optional[str] = None,
        task_id: Optional[str] = None,
        capability: Optional[str] = None,
        provider: Optional[str] = None,
        endpoint: Optional[str] = None,
        request_payload: Optional[Dict[str, Any]] = None,
        response_payload: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[int] = None,
        error: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> None:
        args_hash = sha256_json(request_payload) if request_payload is not None else None

        sql = """
        INSERT INTO trace_events(
          trace_id, session_id, user_id, turn_id, task_id, event_type,
          capability, provider, endpoint, args_hash, idempotency_key,
          status, latency_ms, request_payload, response_payload, error
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                sql,
                (
                    trace_id, session_id, user_id, turn_id, task_id, event_type,
                    capability, provider, endpoint, args_hash, idempotency_key,
                    status, latency_ms,
                    Json(request_payload) if request_payload is not None else None,
                    Json(response_payload) if response_payload is not None else None,
                    error
                ),
            )
            conn.commit()

    def find_by_idempotency_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        sql = """
        SELECT response_payload
        FROM trace_events
        WHERE idempotency_key=%s AND event_type='tool_end' AND status='ok'
        ORDER BY created_at DESC
        LIMIT 1
        """
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(sql, (idempotency_key,)).fetchone()
            return row[0] if row else None