from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException

import psycopg
from psycopg.types.json import Jsonb



# IMPORTANT:
# - We reuse the SAME DSN + SCHEMA/TABLE conventions you already use.
DSN = os.getenv("PROFILE_EVENTS_DB_DSN", "").strip()
SCHEMA = os.getenv("PROFILE_EVENTS_SCHEMA", "public").strip()

EVENTS_TABLE = os.getenv("PROFILE_EVENTS_TABLE", "profile_events").strip()
INSIGHTS_TABLE = os.getenv("PROFILE_INSIGHTS_TABLE", "profile_insights").strip()


def events_fqtn() -> str:
    return f"{SCHEMA}.{EVENTS_TABLE}"


def insights_fqtn() -> str:
    return f"{SCHEMA}.{INSIGHTS_TABLE}"


def _require_dsn() -> None:
    if not DSN:
        raise HTTPException(status_code=500, detail="PROFILE_EVENTS_DB_DSN not set")


router = APIRouter(prefix="/events", tags=["profile_insights"])


# -------------------------
# Phase 2 core computations
# -------------------------

def _norm_scalar(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    s = str(v).strip().lower()
    return s or None


def _norm_list(v: Any) -> List[str]:
    if not isinstance(v, list):
        s = _norm_scalar(v)
        return [s] if s else []
    out: List[str] = []
    for x in v:
        s = _norm_scalar(x)
        if s:
            out.append(s)
    return out


def extract_patterns(
    prefs_payloads: List[Dict[str, Any]],
    *,
    learn_from_sources: tuple[str, ...] = ("query",),
) -> Dict[str, Any]:
    from collections import Counter, defaultdict

    counts = defaultdict(Counter)
    totals = Counter()

    for p in prefs_payloads:
        merged = p.get("merged_prefs") or {}
        sources = p.get("preference_sources") or {}

        for field, raw in merged.items():
            src = sources.get(field, "none")
            if learn_from_sources and src not in learn_from_sources:
                continue

            if isinstance(raw, list):
                for item in _norm_list(raw):
                    counts[field][item] += 1
                    totals[field] += 1
            else:
                s = _norm_scalar(raw)
                if not s:
                    continue
                counts[field][s] += 1
                totals[field] += 1

    patterns: Dict[str, Any] = {}
    for field, c in counts.items():
        t = max(totals[field], 1)
        patterns[field] = {
            k: {"count": v, "share": round(v / t, 4)}
            for k, v in c.most_common()
        }
    return patterns


def stability_scores(
    prefs_payloads: List[Dict[str, Any]],
    *,
    fields: List[str],
) -> Dict[str, float]:
    import math
    from collections import defaultdict

    n = len(prefs_payloads)
    if n == 0:
        return {f: 0.0 for f in fields}

    # exponential weights so recent behaviour matters more
    weights = [math.exp(i / max(n - 1, 1)) for i in range(n)]

    out: Dict[str, float] = {}
    for field in fields:
        bucket = defaultdict(float)
        denom = 0.0

        for i, p in enumerate(prefs_payloads):
            raw = (p.get("merged_prefs") or {}).get(field)
            if raw is None:
                continue
            w = weights[i]

            if isinstance(raw, list):
                key = "|".join(sorted(_norm_list(raw)))
            else:
                key = _norm_scalar(raw) or ""

            if not key:
                continue

            bucket[key] += w
            denom += w

        out[field] = round((max(bucket.values()) if bucket and denom else 0.0) / denom, 4) if denom else 0.0

    return out


def detect_drift(
    prefs_payloads: List[Dict[str, Any]],
    *,
    fields: List[str],
    min_events: int = 12,
) -> Dict[str, Any]:
    from collections import Counter

    n = len(prefs_payloads)
    if n < min_events:
        return {}

    mid = n // 2
    older = prefs_payloads[:mid]
    recent = prefs_payloads[mid:]

    def dominant(keys: List[str]) -> Optional[str]:
        keys = [k for k in keys if k]
        return Counter(keys).most_common(1)[0][0] if keys else None

    drift: Dict[str, Any] = {}

    for field in fields:
        def key_of(p: Dict[str, Any]) -> str:
            raw = (p.get("merged_prefs") or {}).get(field)
            if raw is None:
                return ""
            if isinstance(raw, list):
                return "|".join(sorted(_norm_list(raw)))
            return _norm_scalar(raw) or ""

        from_v = dominant([key_of(p) for p in older])
        to_v = dominant([key_of(p) for p in recent])

        if from_v and to_v and from_v != to_v:
            drift[field] = {"from": from_v, "to": to_v}

    return drift


def build_suggestions(
    *,
    patterns: Dict[str, Any],
    stability: Dict[str, float],
    current_db_prefs: Dict[str, Any],
    stability_threshold: float = 0.75,
    min_share: float = 0.60,
) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []

    for field, dist in patterns.items():
        conf = float(stability.get(field, 0.0))
        if conf < stability_threshold:
            continue

        top_key = next(iter(dist.keys()), None)
        if not top_key:
            continue

        top = dist[top_key]
        if float(top.get("share", 0.0)) < min_share:
            continue

        db_val = current_db_prefs.get(field)
        if isinstance(db_val, list):
            db_norm = "|".join(sorted(_norm_list(db_val)))
        else:
            db_norm = _norm_scalar(db_val)

        if db_norm == top_key:
            continue

        suggestions.append({
            "field": field,
            "proposed_value": top_key,
            "confidence": round(conf, 4),
            "evidence": {"count": top["count"], "share": top["share"]},
            "action": "ask_confirm_save",
        })

    return suggestions


# -----------------------------------
# DB helpers: fetch events + store row
# -----------------------------------

def fetch_prefs_merged_payloads(
    *,
    user_id: str,
    limit: int,
    session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    _require_dsn()

    sql = f"""
        SELECT id, created_at, payload
        FROM {events_fqtn()}
        WHERE user_id = %s
          AND event_type = 'prefs_merged'
          {"AND session_id = %s" if session_id else ""}
        ORDER BY created_at DESC
        LIMIT %s
    """

    params: List[Any] = [user_id]
    if session_id:
        params.append(session_id)
    params.append(limit)

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    # reverse -> oldest to newest for recency weighting
    payloads: List[Dict[str, Any]] = []
    for r in reversed(rows):
        p = r[2] or {}
        if not isinstance(p, dict):
            p = dict(p)
        p["_event_id"] = int(r[0])
        p["_created_at"] = r[1].isoformat() if r[1] else None
        payloads.append(p)

    return payloads


def upsert_profile_insight(
    *,
    user_id: str,
    window_start: Optional[str],
    window_end: Optional[str],
    patterns: Dict[str, Any],
    stability: Dict[str, float],
    drift: Dict[str, Any],
    suggestions: List[Dict[str, Any]],
    insight_meta: Dict[str, Any],
) -> int:
    _require_dsn()

    sql = f"""
    INSERT INTO {insights_fqtn()} (
      user_id, window_start, window_end,
      patterns, stability, drift, suggestions, insight_meta
    )
    VALUES (%s, %s::timestamptz, %s::timestamptz, %s, %s, %s, %s, %s)
    ON CONFLICT (user_id) DO UPDATE SET
      window_start = EXCLUDED.window_start,
      window_end   = EXCLUDED.window_end,
      patterns     = EXCLUDED.patterns,
      stability    = EXCLUDED.stability,
      drift        = EXCLUDED.drift,
      suggestions  = EXCLUDED.suggestions,
      insight_meta = EXCLUDED.insight_meta,
      computed_at  = now()
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
                    Jsonb(patterns),
                    Jsonb(stability),
                    Jsonb(drift),
                    Jsonb(suggestions),
                    Jsonb(insight_meta),
                ),
            )
            insight_id = cur.fetchone()[0]
        conn.commit()

    return int(insight_id)



def fetch_latest_insight(*, user_id: str) -> Optional[Dict[str, Any]]:
    _require_dsn()

    sql = f"""
        SELECT id, user_id, computed_at, window_start, window_end,
               patterns, stability, drift, suggestions, insight_meta
        FROM {insights_fqtn()}
        WHERE user_id = %s
        ORDER BY computed_at DESC
        LIMIT 1
    """

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (user_id,))
            row = cur.fetchone()

    if not row:
        return None

    return {
        "id": str(row[0]),
        "user_id": row[1],
        "computed_at": row[2].isoformat() if row[2] else None,
        "window_start": row[3].isoformat() if row[3] else None,
        "window_end": row[4].isoformat() if row[4] else None,
        "patterns": row[5],
        "stability": row[6],
        "drift": row[7],
        "suggestions": row[8],
        "insight_meta": row[9],
    }


# -------------------------
# Phase 2 endpoints
# -------------------------

@router.post("/users/{user_id}/insights/compute")
def compute_insights(
    user_id: str,
    limit: int = Query(50, ge=5, le=500),
    session_id: Optional[str] = Query(None),
    learn_from: str = Query("query"),  # "query" or "query,db"
) -> Dict[str, Any]:
    payloads = fetch_prefs_merged_payloads(user_id=user_id, limit=limit, session_id=session_id)

    window_start = payloads[0].get("_created_at") if payloads else None
    window_end = payloads[-1].get("_created_at") if payloads else None

    learn_from_sources = tuple(s.strip() for s in learn_from.split(",") if s.strip())
    patterns = extract_patterns(payloads, learn_from_sources=learn_from_sources)
    fields = sorted(patterns.keys())

    stability = stability_scores(payloads, fields=fields)
    drift = detect_drift(payloads, fields=fields)

    # For now you can keep empty; later you fetch from user_service and compare
    current_db_prefs: Dict[str, Any] = {}

    suggestions = build_suggestions(
        patterns=patterns,
        stability=stability,
        current_db_prefs=current_db_prefs,
        stability_threshold=0.75,
        min_share=0.60,
    )

    insight_meta = {
        "limit": limit,
        "events_used": len(payloads),
        "session_id": session_id,
        "learn_from_sources": list(learn_from_sources),
        "thresholds": {"stability": 0.75, "min_share": 0.60},
    }

    insight_id = insert_profile_insight(
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


@router.get("/users/{user_id}/insights/latest")
def latest_insights(user_id: str) -> Dict[str, Any]:
    row = fetch_latest_insight(user_id=user_id)
    if not row:
        raise HTTPException(status_code=404, detail="No insights found")
    return {"ok": True, "data": row}
