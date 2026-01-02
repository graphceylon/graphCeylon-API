from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any, Dict, Optional

from .repo import Phase2Repo
from .compute import extract_patterns, stability_scores, detect_drift, build_suggestions

router = APIRouter()

# Replace this with YOUR orchestrator db pool dependency
def get_db_pool():
    raise NotImplementedError("Wire to your existing asyncpg pool dependency")

# Replace with a real call to your user_service later (Phase 2 still works without it)
async def fetch_db_prefs(user_id: str) -> Dict[str, Any]:
    return {}

@router.post("/events/users/{user_id}/insights/compute")
async def compute_insights(
    user_id: str,
    limit: int = Query(50, ge=5, le=500),
    session_id: Optional[str] = Query(None),
    pool=Depends(get_db_pool),
):
    repo = Phase2Repo(pool)
    payloads = await repo.fetch_prefs_merged(user_id=user_id, limit=limit, session_id=session_id)

    window_start = payloads[0].get("_created_at") if payloads else None
    window_end = payloads[-1].get("_created_at") if payloads else None

    patterns = extract_patterns(payloads, learn_from_sources=("query",))
    fields = sorted(patterns.keys())
    stability = stability_scores(payloads, fields=fields)
    drift = detect_drift(payloads, fields=fields)

    db_prefs = await fetch_db_prefs(user_id)
    suggestions = build_suggestions(
        patterns=patterns,
        stability=stability,
        current_db_prefs=db_prefs,
        stability_threshold=0.75,
        min_share=0.60,
    )

    insight_meta = {
        "limit": limit,
        "events_used": len(payloads),
        "session_id": session_id,
        "learn_from_sources": ["query"],
        "thresholds": {"stability": 0.75, "min_share": 0.60},
    }

    insight_id = await repo.insert_insight(
        user_id=user_id,
        window_start=window_start,
        window_end=window_end,
        patterns=patterns,
        stability=stability,
        drift=drift,
        suggestions=suggestions,
        insight_meta=insight_meta,
    )

    return {
        "ok": True,
        "insight_id": insight_id,
        "user_id": user_id,
        "window_start": window_start,
        "window_end": window_end,
        "patterns": patterns,
        "stability": stability,
        "drift": drift,
        "suggestions": suggestions,
        "insight_meta": insight_meta,
    }

@router.get("/events/users/{user_id}/insights/latest")
async def latest_insights(user_id: str, pool=Depends(get_db_pool)):
    repo = Phase2Repo(pool)
    row = await repo.latest_insight(user_id=user_id)
    if not row:
        raise HTTPException(status_code=404, detail="No insights found")
    return {"ok": True, "data": row}
