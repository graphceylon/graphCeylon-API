from __future__ import annotations
import json, hashlib
from typing import Any, Dict, Optional
from datetime import datetime

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
        # ✅ NEW: transport type tag for benchmark comparisons
        transport_type: Optional[str] = None,
    ) -> None:
        args_hash = sha256_json(request_payload) if request_payload is not None else None

        sql = """
        INSERT INTO trace_events(
          trace_id, session_id, user_id, turn_id, task_id, event_type,
          capability, provider, endpoint, args_hash, idempotency_key,
          status, latency_ms, request_payload, response_payload, error,
          transport_type
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
                    error,
                    transport_type,
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

    # ---- BENCHMARK QUERIES ----
    def get_benchmark_stats(
        self,
        *,
        capability: Optional[str] = None,
        since_hours: int = 24,
    ) -> list[Dict[str, Any]]:
        """
        Returns p50/p95/p99/avg/min/max per transport_type per capability.
        Used by the benchmark dashboard endpoint.
        """
        where_parts = [
            "event_type = 'tool_end'",
            "latency_ms IS NOT NULL",
            "transport_type IS NOT NULL",
            f"created_at > NOW() - INTERVAL '{since_hours} hours'",
        ]
        if capability:
            where_parts.append("capability = %(capability)s")

        where_clause = " AND ".join(where_parts)

        sql = f"""
        SELECT
            transport_type,
            capability,
            COUNT(*)                                                          AS call_count,
            ROUND(AVG(latency_ms))                                            AS avg_ms,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms)::int    AS p50_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms)::int    AS p95_ms,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms)::int    AS p99_ms,
            MIN(latency_ms)                                                   AS min_ms,
            MAX(latency_ms)                                                   AS max_ms,
            ROUND(
                100.0 * SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) / COUNT(*), 2
            )                                                                 AS success_rate
        FROM trace_events
        WHERE {where_clause}
        GROUP BY transport_type, capability
        ORDER BY capability, transport_type
        """
        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute(sql, {"capability": capability}).fetchall()
            cols = [
                "transport_type", "capability", "call_count",
                "avg_ms", "p50_ms", "p95_ms", "p99_ms",
                "min_ms", "max_ms", "success_rate",
            ]
            return [dict(zip(cols, row)) for row in rows]

    def get_benchmark_series(
        self,
        *,
        capability: str,
        transport_type: str,
        limit: int = 100,
    ) -> list[Dict[str, Any]]:
        """
        Returns ordered latency series for a given tool + transport.
        Used for the call-sequence warmup chart.
        """
        sql = """
        SELECT
            ROW_NUMBER() OVER (ORDER BY created_at) AS call_num,
            latency_ms,
            status,
            created_at
        FROM trace_events
        WHERE event_type = 'tool_start'
          AND capability = %s
          AND transport_type = %s
          AND latency_ms IS NOT NULL
        ORDER BY created_at DESC
        LIMIT %s
        """
        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute(sql, (capability, transport_type, limit)).fetchall()
            return [
                {
                    "call_num": r[0],
                    "latency_ms": r[1],
                    "status": r[2],
                    "created_at": str(r[3]),
                }
                for r in rows
            ]