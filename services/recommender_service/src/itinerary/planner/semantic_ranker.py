# semantic_ranker.py

from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict,Any

# Load once at module import (important for performance)
_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def _cosine(u: np.ndarray, v: np.ndarray) -> float:
    return float(np.dot(u, v))


def build_attraction_text(a: Dict) -> str:
    groups = a.get("groups") or []
    groups_txt = " | ".join([str(g) for g in groups if g])

    summary = (a.get("editorial_summary") or "").strip()
    category = (a.get("category") or "").strip()
    religion = (a.get("religion") or "").strip()

    parts = [groups_txt, summary, category, religion]
    return " ; ".join([p for p in parts if p])


def build_query_text(payload: Dict) -> str:
    travel_style = payload.get("travel_style") or []
    tags = payload.get("tags") or []
    activity_pref = payload.get("activity_preference") or ""

    parts = list(travel_style) + list(tags)
    if activity_pref:
        parts.append(activity_pref)

    parts = [str(p).strip() for p in parts if str(p).strip()]
    return " ; ".join(parts) if parts else "general sightseeing"


def attach_semantic_scores(candidates: List[Dict], payload: Dict) -> None:
    if not candidates:
        return

    query_text = build_query_text(payload)
    q_emb = _model.encode([query_text], normalize_embeddings=True)[0]

    texts = [build_attraction_text(c) for c in candidates]
    c_embs = _model.encode(texts, normalize_embeddings=True)

    for c, emb in zip(candidates, c_embs):
        sim = _cosine(q_emb, emb)
        c["_semantic_sim"] = sim
        c["_pref_score"] = sim  # used by your route spread logic

def build_semantic_query(payload: Dict[str, Any] | None) -> str:
    """
    Turns the user payload into a short semantic search query string.
    Keep it stable + simple so results are consistent.
    """
    if not payload:
        return ""

    parts: List[str] = []

    # location intent
    city = payload.get("destination") or payload.get("city")
    if city:
        parts.append(str(city))

    # user preferences that matter semantically
    travel_style = payload.get("travel_style")
    if isinstance(travel_style, list):
        parts.extend([str(x) for x in travel_style if x])

    food = payload.get("food_preferences")
    if isinstance(food, list):
        parts.extend([str(x) for x in food if x])

    raw_text = payload.get("raw_text")
    if raw_text:
        parts.append(str(raw_text))

    # return a compact query
    q = " ".join(parts).strip()
    return q[:300]