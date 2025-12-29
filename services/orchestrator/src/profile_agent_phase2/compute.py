from __future__ import annotations

import os
import json
from typing import Optional, Any, Dict, List, Tuple
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException

# =========================
# ENV / TABLE HELPERS
# =========================

DSN = os.getenv("PROFILE_EVENTS_DB_DSN", "").strip()
SCHEMA = os.getenv("PROFILE_EVENTS_SCHEMA", "public").strip()
EVENTS_TABLE = os.getenv("PROFILE_EVENTS_TABLE", "profile_events").strip()
INSIGHTS_TABLE = os.getenv("PROFILE_INSIGHTS_TABLE", "profile_insights").strip()

PHASE2_AUTO_COMPUTE = os.getenv("PHASE2_AUTO_COMPUTE", "0") == "1"
PHASE2_AUTO_LIMIT = int(os.getenv("PHASE2_AUTO_LIMIT", "50"))
PHASE2_MIN_EVENTS = int(os.getenv("PHASE2_MIN_PREFS_MERGED", "2"))

def events_fqtn() -> str:
    return f"{SCHEMA}.{EVENTS_TABLE}"

def insights_fqtn() -> str:
    return f"{SCHEMA}.{INSIGHTS_TABLE}"

def _require_dsn() -> None:
    if not DSN:
        raise HTTPException(status_code=500, detail="PROFILE_EVENTS_DB_DSN not set")

print("\n========== PHASE2 ENV BOOT ==========")
print("PHASE2_AUTO_COMPUTE =", os.getenv("PHASE2_AUTO_COMPUTE"))
print("PHASE2_MIN_PREFS_MERGED =", os.getenv("PHASE2_MIN_PREFS_MERGED"))
print("PHASE2_AUTO_LIMIT =", os.getenv("PHASE2_AUTO_LIMIT"))
print("PROFILE_EVENTS_SCHEMA =", os.getenv("PROFILE_EVENTS_SCHEMA"))
print("PROFILE_EVENTS_DB_DSN SET =", bool(os.getenv("PROFILE_EVENTS_DB_DSN")))
print("PROFILE_EVENTS_TABLE =", EVENTS_TABLE)
print("PROFILE_INSIGHTS_TABLE =", INSIGHTS_TABLE)
print("====================================\n")


# =========================
# PUBLIC ENTRYPOINT
# =========================

def maybe_auto_compute(user_id: str, session_id: Optional[str] = None) -> bool:
    """
    Auto-compute Phase2 insight snapshot when enough new prefs_merged events exist.
    Writes to profile_insights as UPSERT on (user_id).
    """
    print(f"[phase2] auto_compute check user={user_id} session={session_id}")

    if not PHASE2_AUTO_COMPUTE:
        print("[phase2] auto_compute disabled (PHASE2_AUTO_COMPUTE!=1)")
        return False

    latest_event_ts = _latest_prefs_merged_ts(user_id, session_id=session_id)
    if not latest_event_ts:
        print("[phase2] no prefs_merged yet")
        return False

    latest_insight_ts = _latest_insight_window_end_ts(user_id)
    if latest_insight_ts and latest_event_ts <= latest_insight_ts:
        print("[phase2] no new prefs_merged since last insight")
        return False

    payloads = fetch_prefs_merged_payloads(
        user_id=user_id,
        limit=PHASE2_AUTO_LIMIT,
        session_id=session_id,   # ✅ respect session if passed
    )
    if len(payloads) < PHASE2_MIN_EVENTS:
        print(f"[phase2] not enough prefs_merged ({len(payloads)}/{PHASE2_MIN_EVENTS})")
        return False

    window_start = payloads[0]["_created_at"]
    window_end = payloads[-1]["_created_at"]

    patterns = extract_patterns(payloads, learn_from_sources=("query",))
    fields = sorted(patterns.keys())
    stability = stability_scores(patterns=patterns, fields=fields)
    drift = detect_drift(payloads=payloads, fields=fields)

    suggestions = build_suggestions(
        patterns=patterns,
        stability=stability,
        current_db_prefs={},
        stability_threshold=0.75,
        min_share=0.60,
    )

    insight_meta = {
        "auto": True,
        "limit": PHASE2_AUTO_LIMIT,
        "session_id": session_id,
        "events_used": len(payloads),
        "learn_from_sources": ["query"],
        "thresholds": {"min_share": 0.60, "stability": 0.75},
    }

    insight_id = upsert_profile_insight(
        user_id=user_id,
        window_start=window_start,
        window_end=window_end,
        patterns=patterns,
        stability=stability,
        drift=drift,
        suggestions=suggestions,
        insight_meta=insight_meta,
    )
    print(f"[phase2] upserted insight snapshot id={insight_id}")
    return True


# =========================
# DB READS
# =========================

def _latest_prefs_merged_ts(user_id: str, session_id: Optional[str] = None) -> Optional[datetime]:
    _require_dsn()

    where = "user_id=%s AND event_type='prefs_merged'"
    params: list[Any] = [user_id]
    if session_id:
        where += " AND session_id=%s"
        params.append(session_id)

    sql = f"""
        SELECT created_at
        FROM {events_fqtn()}
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT 1
    """

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
    return row[0] if row else None


def _latest_insight_window_end_ts(user_id: str) -> Optional[datetime]:
    _require_dsn()
    sql = f"""
        SELECT window_end
        FROM {insights_fqtn()}
        WHERE user_id=%s
        ORDER BY computed_at DESC
        LIMIT 1
    """
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id,))
            row = cur.fetchone()
    return row[0] if row else None


def fetch_prefs_merged_payloads(user_id: str, limit: int = 50, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns a list of payload dicts for prefs_merged in ascending time order.
    Adds '_created_at' ISO string to each payload.
    """
    _require_dsn()

    where = "user_id=%s AND event_type='prefs_merged'"
    params: list[Any] = [user_id]
    if session_id:
        where += " AND session_id=%s"
        params.append(session_id)

    sql = f"""
        SELECT created_at, payload
        FROM {events_fqtn()}
        WHERE {where}
        ORDER BY created_at ASC
        LIMIT %s
    """
    params.append(limit)

    out: List[Dict[str, Any]] = []
    with psycopg.connect(DSN) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    for r in rows:
        payload = r["payload"] or {}
        if isinstance(payload, str):
            payload = json.loads(payload)

        # created_at can be timezone-aware depending on DB; keep it safe as ISO.
        created_at: datetime = r["created_at"]
        payload["_created_at"] = created_at.isoformat()
        out.append(payload)

    return out


# =========================
# COMPUTE (SIMPLE BUT WORKING)
# =========================

def _iter_query_fields_from_event_payload(p: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """
    Prefer using preference_sources to only learn values that came from query.
    Fallback to query_overrides if sources missing.
    """
    merged = p.get("merged_prefs") or {}
    sources = p.get("preference_sources") or {}
    q_overrides = p.get("query_overrides") or {}

    # If we have sources, only count merged fields whose source == "query"
    if isinstance(sources, dict) and sources:
        for k, src in sources.items():
            if src == "query" and k in merged:
                yield (k, merged.get(k))
        return

    # fallback: count query_overrides values
    if isinstance(q_overrides, dict):
        for k, v in q_overrides.items():
            yield (k, v)


def extract_patterns(payloads: List[Dict[str, Any]], learn_from_sources=("query",)) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Output shape matches what you showed in DB:
    { field: { value_str: {count:int, share:float} } }
    """
    counts: Dict[str, Dict[str, int]] = {}
    total_events = 0

    for p in payloads:
        total_events += 1
        for field, val in _iter_query_fields_from_event_payload(p):
            if val in [None, "", {}, "unknown"]:
                continue
            if field in {"created_at", "schema_version"}:
                continue

            if isinstance(val, list):
                for item in val:
                    if item in [None, "", "unknown"]:
                        continue
                    counts.setdefault(field, {})
                    counts[field][str(item)] = counts[field].get(str(item), 0) + 1
            else:
                counts.setdefault(field, {})
                counts[field][str(val)] = counts[field].get(str(val), 0) + 1

    patterns: Dict[str, Dict[str, Dict[str, Any]]] = {}
    denom = max(1, total_events)

    for field, m in counts.items():
        patterns[field] = {}
        for v, c in m.items():
            patterns[field][v] = {"count": c, "share": round(c / denom, 4)}

    return patterns


def stability_scores(*, patterns: Dict[str, Dict[str, Dict[str, Any]]], fields: List[str]) -> Dict[str, float]:
    """
    Stability = max share for that field.
    """
    out: Dict[str, float] = {}
    for f in fields:
        vals = patterns.get(f, {})
        best = 0.0
        for meta in vals.values():
            best = max(best, float(meta.get("share", 0.0)))
        out[f] = round(best, 4)
    return out


def detect_drift(payloads: List[Dict[str, Any]], fields: List[str]) -> Dict[str, Any]:
    """
    Stub for now (you can implement later). Keeping {} matches your DB example.
    """
    return {}


def build_suggestions(
    *,
    patterns: Dict[str, Dict[str, Dict[str, Any]]],
    stability: Dict[str, float],
    current_db_prefs: Dict[str, Any],
    stability_threshold: float,
    min_share: float,
) -> List[Dict[str, Any]]:
    """
    Suggest 'ask_confirm_save' for stable fields with high share.
    """
    suggestions: List[Dict[str, Any]] = []
    for field, st in (stability or {}).items():
        if st < stability_threshold:
            continue

        vals = patterns.get(field) or {}
        if not vals:
            continue

        # choose highest share value
        best_val, best_meta = max(vals.items(), key=lambda kv: float(kv[1].get("share", 0.0)))
        if float(best_meta.get("share", 0.0)) < min_share:
            continue

        # do not suggest if db already has same value
        if field in current_db_prefs and str(current_db_prefs[field]) == str(best_val):
            continue

        suggestions.append(
            {
                "field": field,
                "action": "ask_confirm_save",
                "evidence": best_meta,
                "confidence": float(st),
                "proposed_value": best_val,
            }
        )

    return suggestions


# =========================
# DB WRITE (UPSERT)
# =========================

def upsert_profile_insight(
    *,
    user_id: str,
    window_start: str,
    window_end: str,
    patterns: Dict[str, Any],
    stability: Dict[str, Any],
    drift: Dict[str, Any],
    suggestions: List[Dict[str, Any]],
    insight_meta: Dict[str, Any],
) -> str:
    """
    Requires UNIQUE(user_id) on profile_insights.
    Updates the same user's row instead of inserting new rows.
    """
    _require_dsn()

    sql = f"""
    INSERT INTO {insights_fqtn()} (
        user_id, computed_at, window_start, window_end,
        patterns, stability, drift, suggestions, insight_meta
    )
    VALUES (
        %s, NOW(), %s::timestamptz, %s::timestamptz,
        %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb
    )
    ON CONFLICT (user_id) DO UPDATE SET
        computed_at = NOW(),
        window_start = EXCLUDED.window_start,
        window_end   = EXCLUDED.window_end,
        patterns     = EXCLUDED.patterns,
        stability    = EXCLUDED.stability,
        drift        = EXCLUDED.drift,
        suggestions  = EXCLUDED.suggestions,
        insight_meta = EXCLUDED.insight_meta
    RETURNING id
    """

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    user_id,
                    window_start,
                    window_end,
                    json.dumps(patterns),
                    json.dumps(stability),
                    json.dumps(drift),
                    json.dumps(suggestions),
                    json.dumps(insight_meta),
                ),
            )
            row = cur.fetchone()
            conn.commit()

    return str(row[0]) if row else "unknown"
