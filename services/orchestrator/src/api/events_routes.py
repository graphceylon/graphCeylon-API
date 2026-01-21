from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query, HTTPException
import psycopg

router = APIRouter(prefix="/events", tags=["events"])

DSN = os.getenv("PROFILE_EVENTS_DB_DSN", "").strip()
SCHEMA = os.getenv("PROFILE_EVENTS_SCHEMA", "public").strip()
TABLE = os.getenv("PROFILE_EVENTS_TABLE", "profile_events").strip()


def fqtn() -> str:
    return f"{SCHEMA}.{TABLE}"


def _require_dsn() -> None:
    if not DSN:
        raise HTTPException(status_code=500, detail="PROFILE_EVENTS_DB_DSN not set")


# -------------------------
# ✅ Phase-1 Replay helper
# -------------------------
def replay_session_effective_prefs(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Reconstruct effective prefs used for each request in the session.

    Expected event types (your current Phase-1):
      - query_received { raw_text }
      - intent_parsed  { raw_text, confidence, entities, ... }
      - prefs_merged   { db_prefs, query_overrides, merged_prefs, preference_sources }
      - downstream_response { endpoint, ok, response }
    """

    blocks: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}

    def finalize() -> None:
        nonlocal current
        if current:
            blocks.append(current)
            current = {}

    for e in events:
        et = e.get("event_type")
        intent = e.get("intent")
        payload = e.get("payload") or {}

        if et == "query_received":
            finalize()
            current = {
                "user_id": e.get("user_id"),
                "session_id": e.get("session_id"),
                "started_at": e.get("created_at"),
                "raw_text": payload.get("raw_text"),
                "intent": None,
                "intent_confidence": None,
                "entities": None,
                "merged_prefs": None,
                "preference_sources": None,
                "downstream": [],
            }

        elif et == "intent_parsed":
            if not current:
                current = {
                    "user_id": e.get("user_id"),
                    "session_id": e.get("session_id"),
                    "started_at": e.get("created_at"),
                    "raw_text": payload.get("raw_text"),
                    "intent": None,
                    "intent_confidence": None,
                    "entities": None,
                    "merged_prefs": None,
                    "preference_sources": None,
                    "downstream": [],
                }

            current["intent"] = intent
            current["intent_confidence"] = payload.get("confidence")
            current["entities"] = payload.get("entities")
            if payload.get("raw_text"):
                current["raw_text"] = payload.get("raw_text")

        elif et == "prefs_merged":
            if not current:
                current = {
                    "user_id": e.get("user_id"),
                    "session_id": e.get("session_id"),
                    "started_at": e.get("created_at"),
                    "raw_text": None,
                    "intent": intent,
                    "intent_confidence": None,
                    "entities": None,
                    "merged_prefs": None,
                    "preference_sources": None,
                    "downstream": [],
                }

            current["merged_prefs"] = payload.get("merged_prefs")
            current["preference_sources"] = payload.get("preference_sources")

        elif et == "downstream_response":
            if not current:
                current = {
                    "user_id": e.get("user_id"),
                    "session_id": e.get("session_id"),
                    "started_at": None,
                    "raw_text": None,
                    "intent": intent,
                    "intent_confidence": None,
                    "entities": None,
                    "merged_prefs": None,
                    "preference_sources": None,
                    "downstream": [],
                }

            current["downstream"].append(
                {
                    "at": e.get("created_at"),
                    "intent": intent,
                    "endpoint": payload.get("endpoint"),
                    "ok": payload.get("ok"),
                    "response": payload.get("response"),
                }
            )

    finalize()
    return blocks


# -------------------------
# Existing endpoints (kept)
# -------------------------
@router.get("/health")
def events_health() -> Dict[str, Any]:
    if not DSN:
        return {"ok": False, "error": "PROFILE_EVENTS_DB_DSN not set"}
    try:
        with psycopg.connect(DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return {"ok": True, "table": fqtn()}
    except Exception as ex:
        return {"ok": False, "error": str(ex)}


@router.get("/by-user/{user_id}")
def get_events_by_user(
    user_id: str,
    limit: int = Query(50, ge=1, le=500),
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    _require_dsn()

    base_sql = f"""
        SELECT id, user_id, session_id, created_at, event_type, intent, payload
        FROM {fqtn()}
        WHERE user_id = %s
    """
    params: List[Any] = [user_id]

    if session_id:
        base_sql += " AND session_id = %s"
        params.append(session_id)

    base_sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(base_sql, params)
            rows = cur.fetchall()

    events = []
    for r in rows:
        events.append(
            {
                "id": str(r[0]),
                "user_id": r[1],
                "session_id": r[2],
                "created_at": r[3].isoformat() if r[3] else None,
                "event_type": r[4],
                "intent": r[5],
                "payload": r[6],
            }
        )

    return {"ok": True, "count": len(events), "events": events}


# -------------------------
# ✅ New Phase-1 endpoints
# -------------------------

@router.get("/users/{user_id}/recent")
def get_recent_events(
    user_id: str,
    limit: int = Query(50, ge=1, le=500),
    event_type: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    Fetch last N events by user_id ordered by created_at DESC.
    Optional: filter by event_type.
    """
    _require_dsn()

    sql = f"""
        SELECT id, user_id, session_id, created_at, event_type, intent, payload
        FROM {fqtn()}
        WHERE user_id = %s
        {"AND event_type = %s" if event_type else ""}
        ORDER BY created_at DESC
        LIMIT %s
    """

    params: List[Any] = [user_id]
    if event_type:
        params.append(event_type)
    params.append(limit)

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    events = [
        {
            "id": str(r[0]),
            "user_id": r[1],
            "session_id": r[2],
            "created_at": r[3].isoformat() if r[3] else None,
            "event_type": r[4],
            "intent": r[5],
            "payload": r[6],
        }
        for r in rows
    ]

    return {
        "ok": True,
        "user_id": user_id,
        "limit": limit,
        "event_type": event_type,
        "count": len(events),
        "events": events,
    }


@router.get("/users/{user_id}/sessions")
def list_user_sessions(
    user_id: str,
    limit: int = Query(50, ge=1, le=500),
) -> Dict[str, Any]:
    """
    List sessions for a user with counts + time range.
    Helps debugging + Phase-2 preparation.
    """
    _require_dsn()

    sql = f"""
        SELECT
            session_id,
            COUNT(*)::int AS event_count,
            MIN(created_at) AS first_seen,
            MAX(created_at) AS last_seen
        FROM {fqtn()}
        WHERE user_id = %s
          AND session_id IS NOT NULL
          AND session_id <> ''
        GROUP BY session_id
        ORDER BY last_seen DESC
        LIMIT %s
    """

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id, limit))
            rows = cur.fetchall()

    sessions = [
        {
            "session_id": r[0],
            "event_count": r[1],
            "first_seen": r[2].isoformat() if r[2] else None,
            "last_seen": r[3].isoformat() if r[3] else None,
        }
        for r in rows
    ]

    return {"ok": True, "user_id": user_id, "count": len(sessions), "sessions": sessions}


@router.get("/sessions/{session_id}/replay")
def replay_session(session_id: str) -> Dict[str, Any]:
    """
    Replay a session and reconstruct effective prefs used per request.
    """
    _require_dsn()

    session_id = (session_id or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    sql = f"""
        SELECT id, user_id, session_id, created_at, event_type, intent, payload
        FROM {fqtn()}
        WHERE session_id = %s
        ORDER BY created_at ASC
    """

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (session_id,))
            rows = cur.fetchall()

    events = [
        {
            "id": str(r[0]),
            "user_id": r[1],
            "session_id": r[2],
            "created_at": r[3].isoformat() if r[3] else None,
            "event_type": r[4],
            "intent": r[5],
            "payload": r[6],
        }
        for r in rows
    ]

    if not events:
        raise HTTPException(status_code=404, detail="No events found for this session")

    timeline = replay_session_effective_prefs(events)

    return {
        "ok": True,
        "session_id": session_id,
        "event_count": len(events),
        "timeline": timeline,
    }
