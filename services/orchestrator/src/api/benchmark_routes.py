"""
benchmark_routes.py
-------------------
FastAPI router exposing latency benchmark data from PostgresTraceStore.
Add to main.py:
    from .benchmark_routes import router as benchmark_router
    app.include_router(benchmark_router, prefix="/benchmark")
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["benchmark"])


def _get_store():
    from ..orchestrator_core.runtime.trace_pg import PostgresTraceStore
    dsn = os.getenv("ORCH_DB_DSN", "").strip()
    if not dsn:
        raise HTTPException(status_code=503, detail="ORCH_DB_DSN not configured")
    return PostgresTraceStore(dsn)


@router.get("/stats")
def get_stats(
    capability: Optional[str] = Query(None, description="Filter by intent name e.g. forecast_weather"),
    since_hours: int = Query(24, description="Look back window in hours"),
    date: Optional[str] = Query(None, description="Fixed date filter in YYYY-MM-DD format"),
):
    """
    Returns p50/p95/p99/avg/min/max per transport_type per capability.
    """
    store = _get_store()
    rows = store.get_benchmark_stats(
        capability=capability,
        since_hours=since_hours,
        date=date,
    )
    return {"ok": True, "stats": rows, "since_hours": since_hours, "date": date}


@router.get("/series")
def get_series(
    capability: str = Query(..., description="Intent name e.g. forecast_weather"),
    transport: str = Query(..., description="Transport type e.g. a2a_http"),
    limit: int = Query(100, description="Max data points"),
    date: Optional[str] = Query(None, description="Fixed date filter in YYYY-MM-DD format"),
):
    """
    Returns ordered latency series for a given tool + transport.
    Used for the call-sequence warmup chart.
    """
    store = _get_store()
    rows = store.get_benchmark_series(
        capability=capability,
        transport_type=transport,
        limit=limit,
        date=date,
    )
    return {
        "ok": True,
        "series": rows,
        "capability": capability,
        "transport": transport,
        "date": date,
    }


@router.get("/summary")
def get_summary(
    since_hours: int = Query(24, description="Look back window in hours"),
    date: Optional[str] = Query(None, description="Fixed date filter in YYYY-MM-DD format"),
):
    """
    Returns all stats for all intents + transports grouped by capability.
    Used by the full benchmark dashboard.
    """
    store = _get_store()
    rows = store.get_benchmark_stats(since_hours=since_hours, date=date)

    grouped: dict = {}
    for row in rows:
        cap = row["capability"] or "unknown"
        if cap not in grouped:
            grouped[cap] = {}
        grouped[cap][row["transport_type"]] = {
            k: v for k, v in row.items()
            if k not in ("capability", "transport_type")
        }

    return {
        "ok": True,
        "summary": grouped,
        "since_hours": since_hours,
        "date": date,
        "transport_types": list({r["transport_type"] for r in rows}),
        "capabilities": list(grouped.keys()),
    }