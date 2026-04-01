# # semantic_ranker.py

# from sentence_transformers import SentenceTransformer
# import numpy as np
# from typing import List, Dict,Any

# # Load once at module import (important for performance)
# _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


# def _cosine(u: np.ndarray, v: np.ndarray) -> float:
#     return float(np.dot(u, v))


# def build_attraction_text(a: Dict) -> str:
#     groups = a.get("groups") or []
#     groups_txt = " | ".join([str(g) for g in groups if g])

#     summary = (a.get("editorial_summary") or "").strip()
#     category = (a.get("category") or "").strip()
#     religion = (a.get("religion") or "").strip()

#     parts = [groups_txt, summary, category, religion]
#     return " ; ".join([p for p in parts if p])


# def build_query_text(payload: Dict) -> str:
#     travel_style = payload.get("travel_style") or []
#     tags = payload.get("tags") or []
#     activity_pref = payload.get("activity_preference") or ""

#     parts = list(travel_style) + list(tags)
#     if activity_pref:
#         parts.append(activity_pref)

#     parts = [str(p).strip() for p in parts if str(p).strip()]
#     return " ; ".join(parts) if parts else "general sightseeing"


# def attach_semantic_scores(candidates: List[Dict], payload: Dict) -> None:
#     if not candidates:
#         return

#     query_text = build_query_text(payload)
#     q_emb = _model.encode([query_text], normalize_embeddings=True)[0]

#     texts = [build_attraction_text(c) for c in candidates]
#     c_embs = _model.encode(texts, normalize_embeddings=True)

#     for c, emb in zip(candidates, c_embs):
#         sim = _cosine(q_emb, emb)
#         c["_semantic_sim"] = sim
#         c["_pref_score"] = sim  # used by your route spread logic

# def build_semantic_query(payload: Dict[str, Any] | None) -> str:
#     """
#     Turns the user payload into a short semantic search query string.
#     Keep it stable + simple so results are consistent.
#     """
#     if not payload:
#         return ""

#     parts: List[str] = []

#     # location intent
#     city = payload.get("destination") or payload.get("city")
#     if city:
#         parts.append(str(city))

#     # user preferences that matter semantically
#     travel_style = payload.get("travel_style")
#     if isinstance(travel_style, list):
#         parts.extend([str(x) for x in travel_style if x])

#     food = payload.get("food_preferences")
#     if isinstance(food, list):
#         parts.extend([str(x) for x in food if x])

#     raw_text = payload.get("raw_text")
#     if raw_text:
#         parts.append(str(raw_text))

#     # return a compact query
#     q = " ".join(parts).strip()
#     return q[:300]

# semantic_ranker.py

from __future__ import annotations

import os
import re
from typing import List, Dict, Any, Optional

import httpx


KG_BASE_URL = os.getenv("KG_BASE_URL", "http://localhost:8000").rstrip("/")
KG_VECTOR_SEARCH_PATH = "/sub-attractions/search/vector"


def _norm_text(x: Optional[str]) -> str:
    if not x:
        return ""
    x = str(x).lower().strip()
    x = re.sub(r"\s+", " ", x)
    x = re.sub(r"[^a-z0-9 ]", "", x)
    return x


def _join_keys(item: Dict[str, Any]) -> List[str]:
    """
    Create stable fallback keys so vector results can be merged back into planner candidates.
    Priority:
      1) googlePlaceId / google_place_id
      2) normalized name/title + district
      3) normalized name/title + city
      4) normalized name/title only
    """
    keys: List[str] = []

    gpid = item.get("googlePlaceId") or item.get("google_place_id")
    if gpid:
        keys.append(f"gpid:{str(gpid).strip()}")

    name = _norm_text(item.get("title") or item.get("name") or "")
    district = _norm_text(item.get("district") or "")
    city = _norm_text(item.get("city") or "")

    if name and district:
        keys.append(f"nd:{name}|{district}")
    if name and city:
        keys.append(f"nc:{name}|{city}")
    if name:
        keys.append(f"n:{name}")

    return keys


def build_semantic_query(payload: Dict[str, Any] | None) -> str:
    """
    Turns the user payload into a compact semantic search query string.
    Priority:
      - raw_text
      - travel_style
      - tags
      - activity_preference
      - food_preferences
      - destination/city
    """
    if not payload:
        return ""

    parts: List[str] = []

    raw_text = payload.get("raw_text")
    if raw_text:
        parts.append(str(raw_text).strip())

    travel_style = payload.get("travel_style")
    if isinstance(travel_style, list):
        parts.extend([str(x).strip() for x in travel_style if str(x).strip()])

    tags = payload.get("tags")
    if isinstance(tags, list):
        parts.extend([str(x).strip() for x in tags if str(x).strip()])

    activity_pref = payload.get("activity_preference")
    if activity_pref:
        parts.append(str(activity_pref).strip())

    food = payload.get("food_preferences")
    if isinstance(food, list):
        parts.extend([str(x).strip() for x in food if str(x).strip()])

    city = payload.get("destination") or payload.get("city")
    if city:
        parts.append(str(city).strip())

    # dedupe while preserving order
    seen = set()
    compact: List[str] = []
    for p in parts:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            compact.append(p)

    q = " ".join(compact).strip()
    return q[:300]


def _fetch_vector_results(
    *,
    payload: Dict[str, Any],
    timeout: float = 20.0,
    top_k: int = 80,
) -> List[Dict[str, Any]]:
    query = build_semantic_query(payload)
    if not query:
        return []

    url = f"{KG_BASE_URL}{KG_VECTOR_SEARCH_PATH}"
    params = {
        "query": query,
        "limit": min(top_k, 50),      # endpoint max is 50
        "similarity_threshold": 0.5,  # 0.7 default is too strict, misses good matches
    }

    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, params=params)  # POST + query params, no body
        r.raise_for_status()
        data = r.json()

    items = data.get("results") or []  # endpoint uses "results" not "items"
    return [x for x in items if isinstance(x, dict)]


def attach_semantic_scores(candidates: List[Dict[str, Any]], payload: Dict[str, Any]) -> None:
    """
    Enrich already-fetched planner candidates with semantic similarity returned by
    /sub-attractions/search/vector.

    This does NOT replace candidate retrieval.
    It only attaches:
      - _semantic_sim
      - _semantic_source
      - _pref_score (for your existing route logic compatibility)
    """
    if not candidates:
        return

    # initialize defaults first
    for c in candidates:
        c["_semantic_sim"] = float(c.get("_semantic_sim", 0.0) or 0.0)
        c["_semantic_source"] = c.get("_semantic_source")

    query = build_semantic_query(payload)
    if not query:
        return

    try:
        semantic_items = _fetch_vector_results(payload=payload, timeout=20.0, top_k=80)
    except Exception as exc:
        print(f"[SEMANTIC] vector endpoint failed: {exc}")
        return

    if not semantic_items:
        print("[SEMANTIC] vector endpoint returned 0 items")
        return

    sem_map: Dict[str, float] = {}

    for s in semantic_items:
        sim = float(s.get("similarity", 0.0) or 0.0)
        for key in _join_keys(s):
            sem_map[key] = max(sem_map.get(key, 0.0), sim)

    matched = 0
    for c in candidates:
        best = float(c.get("_semantic_sim", 0.0) or 0.0)
        for key in _join_keys(c):
            best = max(best, sem_map.get(key, 0.0))

        c["_semantic_sim"] = best
        c["_semantic_source"] = "vector_endpoint" if best > 0 else None

        # keep compatibility with any older planner logic using _pref_score
        # but do NOT overwrite if a stronger pref score already exists later
        if "_pref_score" not in c or not c["_pref_score"]:
            c["_pref_score"] = best

        if best > 0:
            matched += 1

    print(
        f"[SEMANTIC] query={query!r} | "
        f"vector_items={len(semantic_items)} | "
        f"candidate_matches={matched}/{len(candidates)}"
    )