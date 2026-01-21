from __future__ import annotations

import os
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg.rows import dict_row

from sentence_transformers import SentenceTransformer


# -------------------------
# Settings
# -------------------------
PROFILE_EVENTS_DB_DSN = os.getenv("PROFILE_EVENTS_DB_DSN", "").strip()
PROFILE_EVENTS_SCHEMA = os.getenv("PROFILE_EVENTS_SCHEMA", "public").strip()
EMBEDDINGS_TABLE = os.getenv("PROFILE_MEMORY_EMBEDDINGS_TABLE", "profile_memory_embeddings").strip()

# Embed model should match what you used for storing memory embeddings (same dim).
EMBED_MODEL_NAME = os.getenv("PHASE3_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2").strip()


def _require_dsn() -> None:
    if not PROFILE_EVENTS_DB_DSN:
        raise RuntimeError("PROFILE_EVENTS_DB_DSN not set")


def _fqtn(table: str) -> str:
    return f"{PROFILE_EVENTS_SCHEMA}.{table}"


# -------------------------
# Embedder
# -------------------------
class STEmbedder:
    """
    SentenceTransformer wrapper that returns L2-normalized embeddings.
    Normalization makes cosine similarity stable.
    """
    def __init__(self, model_name: str = EMBED_MODEL_NAME):
        self.model = SentenceTransformer(model_name)

    def embed(self, text: str) -> List[float]:
        vec = self.model.encode(text, normalize_embeddings=True)
        # vec is numpy array; convert to python floats
        return [float(x) for x in vec]


# -------------------------
# Recall result types
# -------------------------
@dataclass
class RecallHit:
    similarity: float
    event_type: str
    created_at: str
    snippet: str
    meta: Dict[str, Any]
    reasons: List[str]


# -------------------------
# Explainability (truthful reasons)
# -------------------------
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


def build_reasons(
    query_meta: Dict[str, Any],
    hit_meta: Dict[str, Any],
) -> List[str]:
    """
    Generates reasons ONLY from metadata overlap.
    Never invents fields.
    """
    reasons: List[str] = []

    # 1) Overlap matches on common keys
    for k in OVERLAP_KEYS:
        qv = query_meta.get(k)
        hv = hit_meta.get(k)

        qs = _as_set(qv)
        hs = _as_set(hv)
        overlap = qs.intersection(hs)

        if overlap:
            # Format nicely
            if len(overlap) == 1:
                reasons.append(f"Matched {k}: {next(iter(overlap))}")
            else:
                reasons.append(f"Matched {k}: {', '.join(sorted(overlap))}")

    # 2) Explicitness from preference_sources (if present in hit meta)
    # Example: hit_meta["preference_sources"] = {"budget_level": "query", ...}
    pref_sources = hit_meta.get("preference_sources")
    if isinstance(pref_sources, dict):
        explicit_fields = [k for k, src in pref_sources.items() if str(src).lower() == "query"]
        if explicit_fields:
            # keep short + stable
            explicit_fields = sorted(explicit_fields)[:6]
            reasons.append("Previously user-explicit fields: " + ", ".join(explicit_fields))

    # 3) If no reasons found, still return stable “semantic similarity”
    if not reasons:
        reasons.append("Semantically similar past memory (no explicit metadata overlap)")

    # Deduplicate while preserving order
    seen = set()
    out = []
    for r in reasons:
        if r not in seen:
            out.append(r)
            seen.add(r)
    return out


# -------------------------
# Recall query builder
# -------------------------
def build_query_meta(request_summary: str, extracted: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Minimal meta for the query-side. If you have your own intent/prefs parser output,
    pass it in via `extracted` and we’ll use it.
    """
    meta = {"q": request_summary}
    if isinstance(extracted, dict):
        meta.update(extracted)
    return meta


# -------------------------
# pgvector recall
# -------------------------
def recall_memories(
    user_id: str,
    request_summary: str,
    k: int = 5,
    event_types: Optional[List[str]] = None,
    extracted_query_meta: Optional[Dict[str, Any]] = None,
    snippet_chars: int = 240,
) -> List[RecallHit]:
    """
    Semantic recall:
    - embeds request_summary
    - searches profile_memory_embeddings by user_id (+ optional event_types)
    - returns top-k hits with similarity + reasons
    """
    _require_dsn()

    if not request_summary.strip():
        return []

    embedder = STEmbedder()
    q_vec = embedder.embed(request_summary.strip())

    fq = _fqtn(EMBEDDINGS_TABLE)
    event_types = event_types or ["prefs_merged", "intent_parsed", "downstream_response"]

    # NOTE:
    # vector cosine distance operator is: <=>  (pgvector)
    # similarity = 1 - distance (when using cosine distance)
    sql = f"""
        SELECT
            event_type,
            created_at,
            doc_text,
            meta,
            (1 - (embedding <=> %s::vector)) AS similarity
        FROM {fq}
        WHERE user_id = %s
          AND event_type = ANY(%s)
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """

    hits: List[RecallHit] = []
    query_meta = build_query_meta(request_summary, extracted_query_meta)

    with psycopg.connect(PROFILE_EVENTS_DB_DSN, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (q_vec, user_id, event_types, q_vec, k))
            rows = cur.fetchall()

    for r in rows:
        meta = r.get("meta") or {}
        doc_text = (r.get("doc_text") or "").strip()
        snippet = doc_text[:snippet_chars] + ("…" if len(doc_text) > snippet_chars else "")

        sim = float(r.get("similarity") or 0.0)
        # clamp for safety
        sim = max(-1.0, min(1.0, sim))

        reasons = build_reasons(query_meta, meta)

        created_at = r.get("created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        hits.append(
            RecallHit(
                similarity=sim,
                event_type=str(r.get("event_type") or ""),
                created_at=str(created_at or ""),
                snippet=snippet,
                meta=meta,
                reasons=reasons,
            )
        )

    return hits
