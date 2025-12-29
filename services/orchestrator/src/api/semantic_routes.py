from __future__ import annotations

from fastapi import APIRouter, Query
from typing import Any, Dict, List, Optional

from ..profile_semantic.pipeline import run_embed_pipeline
from ..profile_semantic.db import db_conn
from ..profile_semantic.embedder import embed_texts, vector_literal
from ..profile_semantic.settings import DEFAULT_TOP_K

router = APIRouter(prefix="/profile/semantic", tags=["semantic"])


# -----------------------------
# Explainability helpers
# -----------------------------
OVERLAP_KEYS = [
    "city",
    "homeCity",
    "district",
    "province",
    "travel_style",
    "food_preferences",
    "budget_level",
    "avoid_crowds",
    "pace_preference",
    "accommodation_type",
    "preferred_transport",
    "activity_preference",
]

def _as_set(v: Any) -> set:
    if v is None:
        return set()
    if isinstance(v, list):
        return set([str(x).strip().lower() for x in v if str(x).strip()])
    return set([str(v).strip().lower()]) if str(v).strip() else set()


def build_reasons(query_meta: Dict[str, Any], hit_meta: Dict[str, Any]) -> List[str]:
    """
    Truthful reasons ONLY from metadata overlap + explicitness from preference_sources.
    Never hallucinate fields that aren't present.
    """
    reasons: List[str] = []

    # 1) overlap on common keys
    for k in OVERLAP_KEYS:
        qs = _as_set(query_meta.get(k))
        hs = _as_set(hit_meta.get(k))
        overlap = qs.intersection(hs)
        if overlap:
            if len(overlap) == 1:
                reasons.append(f"Matched {k}: {next(iter(overlap))}")
            else:
                reasons.append(f"Matched {k}: {', '.join(sorted(overlap))}")

    # 2) highlight previously user-explicit fields (if present)
    pref_sources = hit_meta.get("preference_sources")
    if isinstance(pref_sources, dict):
        explicit_fields = [k for k, src in pref_sources.items() if str(src).lower() == "query"]
        if explicit_fields:
            explicit_fields = sorted(explicit_fields)[:6]
            reasons.append("Previously user-explicit fields: " + ", ".join(explicit_fields))

    # 3) fallback
    if not reasons:
        reasons.append("Semantically similar past memory (no explicit metadata overlap)")

    # dedupe keep order
    seen = set()
    out = []
    for r in reasons:
        if r not in seen:
            out.append(r)
            seen.add(r)
    return out


def build_query_meta_from_q(q: str) -> Dict[str, Any]:
    """
    Minimal query meta. If you later have intent/prefs parsing output,
    you can extend this to include city/travel_style/etc.
    """
    return {"q": q}


# -----------------------------
# Routes
# -----------------------------
@router.post("/embed")
def embed_user(user_id: str, limit: int = 500):
    return run_embed_pipeline(user_id=user_id, limit=limit)


@router.get("/recall")
def recall(
    user_id: str,
    q: str = Query(..., min_length=2),
    k: int = Query(DEFAULT_TOP_K, ge=1, le=20),
    event_types: Optional[str] = Query(
        None,
        description="Comma-separated list. Default: prefs_merged,intent_parsed,downstream_response",
    ),
    snippet_chars: int = Query(240, ge=40, le=1000),
):
    """
    Semantic recall:
    - embed q
    - pgvector search
    - return similarity + truthful reasons based on metadata overlap
    """
    v = embed_texts([q])[0]
    vlit = vector_literal(v)

    # default event type filter
    types = [t.strip() for t in (event_types or "").split(",") if t.strip()]
    if not types:
        types = ["prefs_merged", "intent_parsed", "downstream_response"]

    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT event_type, created_at, doc_text, meta,
                   (embedding <=> %s::vector) AS distance
            FROM profile_memory_embeddings
            WHERE user_id=%s
              AND event_type = ANY(%s)
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (vlit, user_id, types, vlit, k),
        ).fetchall()

    query_meta = build_query_meta_from_q(q)

    results: List[Dict[str, Any]] = []
    for (etype, created_at, doc_text, meta, distance) in rows:
        meta_dict: Dict[str, Any] = meta if isinstance(meta, dict) else {}

        # cosine similarity when using cosine distance:
        # similarity = 1 - distance
        dist = float(distance)
        similarity = 1.0 - dist

        text = (doc_text or "").strip()
        snippet = text[:snippet_chars] + ("…" if len(text) > snippet_chars else "")

        reasons = build_reasons(query_meta=query_meta, hit_meta=meta_dict)

        results.append(
            {
                "event_type": etype,
                "created_at": created_at,
                "distance": dist,
                "similarity": similarity,
                "reasons": reasons,
                "meta": meta_dict,
                "snippet": snippet,
                "doc_text": doc_text,  # keep full text for dev; you can remove later
            }
        )

    return {
        "ok": True,
        "user_id": user_id,
        "q": q,
        "k": k,
        "event_types": types,
        "results": results,
    }
