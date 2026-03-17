# preference_embedder.py
from __future__ import annotations

import json
import math
import os
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── reuse your existing embedder ──────────────────────────────────────────────
# This is the SAME function you use in profile_semantic
from services.orchestrator.src.profile_semantic.embedder import embed_texts

# ── where we cache attraction embeddings on disk ─────────────────────────────
_CACHE_PATH = Path(__file__).resolve().parent / "_attraction_embedding_cache.pkl"

# ── preference → rich descriptive query ──────────────────────────────────────
# These are NOT keyword lists — they are natural language descriptions
# that the embedding model will understand semantically.
PREFERENCE_QUERIES: Dict[str, str] = {
    "eco-friendly": (
        "eco-friendly nature reserve wildlife sanctuary rainforest "
        "botanical garden hiking trail waterfall scenic park sustainable tourism"
    ),
    "cultural": (
        "ancient temple heritage site museum historical ruins sacred Buddhist "
        "Hindu site dagoba stupa fort palace colonial landmark"
    ),
    "adventure": (
        "hiking trekking rock climbing white water rafting surfing scuba diving "
        "safari zip line canyon waterfall adventure sports extreme outdoor"
    ),
    "family-friendly": (
        "family kids children park zoo aquarium beach playground garden "
        "safe educational fun interactive outdoor activities"
    ),
    "romantic": (
        "romantic couples sunset viewpoint scenic hilltop lake garden "
        "lighthouse peaceful serene intimate getaway honeymoon"
    ),
    "relaxation": (
        "peaceful calm quiet relaxing spa beach garden lake viewpoint "
        "scenic walk sunset serene nature retreat meditation"
    ),
}

# ── cached preference vectors (built once per process) ───────────────────────
_pref_vector_cache: Dict[str, List[float]] = {}


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _get_pref_vector(key: str) -> Optional[List[float]]:
    """
    Returns (and caches) the embedding vector for a preference key.
    Built once per process lifetime.
    """
    if key in _pref_vector_cache:
        return _pref_vector_cache[key]

    query = PREFERENCE_QUERIES.get(key)
    if not query:
        return None

    try:
        vec = embed_texts([query])[0]
        _pref_vector_cache[key] = vec
        return vec
    except Exception as e:
        print(f"[preference_embedder] failed to embed pref key={key}: {e}")
        return None


def _attraction_text(rec: Dict[str, Any]) -> str:
    """
    Build a rich text blob from an attraction record.
    The richer this is, the better the embedding match.
    """
    parts = [
        rec.get("title") or rec.get("name") or "",
        rec.get("category") or "",
        rec.get("description") or rec.get("editorial_summary") or "",
        rec.get("tags") or "",
        rec.get("district") or "",
        rec.get("city") or "",
        rec.get("province") or "",
    ]
    return " ".join(str(p) for p in parts if p).strip()


# ── attraction embedding cache (disk-backed) ──────────────────────────────────

def _load_cache() -> Dict[str, List[float]]:
    if _CACHE_PATH.exists():
        try:
            with open(_CACHE_PATH, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache: Dict[str, List[float]]) -> None:
    try:
        with open(_CACHE_PATH, "wb") as f:
            pickle.dump(cache, f)
    except Exception as e:
        print(f"[preference_embedder] cache save failed: {e}")


# In-memory attraction vector store (loaded from disk once per process)
_attraction_cache: Optional[Dict[str, List[float]]] = None


def _get_attraction_vector(rec: Dict[str, Any]) -> Optional[List[float]]:
    """
    Returns the embedding for an attraction.
    Uses a disk cache keyed by attraction_id so we don't re-embed
    the same attraction on every request.
    """
    global _attraction_cache
    if _attraction_cache is None:
        _attraction_cache = _load_cache()

    aid = rec.get("attraction_id")
    if not aid:
        return None

    if aid in _attraction_cache:
        return _attraction_cache[aid]

    # not in cache → embed now and save
    text = _attraction_text(rec)
    if not text:
        return None

    try:
        vec = embed_texts([text])[0]
        _attraction_cache[aid] = vec
        _save_cache(_attraction_cache)   # persist immediately
        return vec
    except Exception as e:
        print(f"[preference_embedder] embed attraction {aid} failed: {e}")
        return None


# ── PUBLIC API ────────────────────────────────────────────────────────────────

def score_attraction_for_preference(
    rec: Dict[str, Any],
    preference_key: str,
) -> float:
    """
    Returns 0..1 cosine similarity between:
      - the attraction's text embedding
      - the preference query embedding

    This REPLACES _matches_priority() in itinerary_planner.py
    """
    pref_vec = _get_pref_vector(preference_key)
    if pref_vec is None:
        return 0.0

    att_vec = _get_attraction_vector(rec)
    if att_vec is None:
        return 0.0

    raw = _cosine(pref_vec, att_vec)

    # cosine similarity for sentence embeddings typically ranges 0.2–0.9
    # normalise so that:
    #   < 0.35  →  0.0  (irrelevant)
    #   0.35–0.5 → 0.0–0.5 (weak match)
    #   0.5–0.7  → 0.5–0.9 (good match)
    #   > 0.7    → 1.0  (strong match)
    if raw < 0.35:
        return 0.0
    normalized = (raw - 0.35) / (0.70 - 0.35)   # map 0.35..0.70 → 0..1
    return float(min(1.0, max(0.0, normalized)))


def precompute_attraction_embeddings(candidates: List[Dict[str, Any]]) -> None:
    """
    Call this once per batch of candidates to pre-embed them all
    in one shot (much faster than one-by-one).
    Skips any that are already cached.
    """
    global _attraction_cache
    if _attraction_cache is None:
        _attraction_cache = _load_cache()

    # find which ones need embedding
    to_embed: List[Tuple[str, str]] = []   # (attraction_id, text)
    for rec in candidates:
        aid = rec.get("attraction_id")
        if aid and aid not in _attraction_cache:
            text = _attraction_text(rec)
            if text:
                to_embed.append((aid, text))

    if not to_embed:
        return   # all cached

    print(f"[preference_embedder] embedding {len(to_embed)} new attractions...")
    try:
        texts = [t for _, t in to_embed]
        vectors = embed_texts(texts)   # batch call — much faster

        for (aid, _), vec in zip(to_embed, vectors):
            _attraction_cache[aid] = vec

        _save_cache(_attraction_cache)
        print(f"[preference_embedder] cached {len(to_embed)} attractions to disk")

    except Exception as e:
        print(f"[preference_embedder] batch embed failed: {e}")