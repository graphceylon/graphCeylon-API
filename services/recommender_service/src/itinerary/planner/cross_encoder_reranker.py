from __future__ import annotations
from functools import lru_cache
from typing import Any, Dict, List, Optional

from sentence_transformers import CrossEncoder


DEFAULT_CE_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_cross_encoder(model_name: str = DEFAULT_CE_MODEL) -> CrossEncoder:
    return CrossEncoder(model_name, max_length=512)


def _clean_parts(parts: List[Any]) -> List[str]:
    out: List[str] = []
    seen = set()

    for p in parts:
        s = str(p or "").strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)

    return out


def build_resolved_ce_query(payload: Optional[Dict[str, Any]]) -> str:
    if not payload:
        return "general sightseeing"

    raw_text = str(payload.get("raw_text") or "").strip()

    destination = payload.get("destination") or payload.get("city")
    travel_style = payload.get("travel_style") or []
    tags = payload.get("tags") or []
    activity_preference = payload.get("activity_preference")
    food_preferences = payload.get("food_preferences") or []
    preferred_transport = payload.get("preferred_transport") or []
    budget_level = payload.get("budget_level")
    pace_preference = payload.get("pace_preference")
    avoid_crowds = payload.get("avoid_crowds")
    rain_preference = payload.get("rain_preference")

    parts: List[Any] = []

    if raw_text:
        parts.append(raw_text)

    if destination:
        parts.append(destination)

    # ✅ ENHANCED: Amplify cultural/heritage intent
    combined_tags = set()
    if isinstance(tags, list):
        combined_tags.update(tags)
    if isinstance(travel_style, list):
        combined_tags.update(travel_style)
    
    # Check if query intent is cultural/heritage focused
    is_cultural_intent = any(
        keyword in str(combined_tags).lower() or keyword in raw_text.lower()
        for keyword in ["cultural", "heritage", "historical", "religious", "spiritual", 
                       "temple", "monastery", "sacred", "archaeological", "historical site"]
    )
    
    # ✅ If cultural intent detected, amplify cultural keywords
    if is_cultural_intent:
        if "cultural" not in raw_text.lower():
            parts.append("cultural heritage")
        parts.append("religious significance")
        parts.append("historical importance")
    
    # query tags get priority over DB travel_style
    if isinstance(tags, list) and tags:
        parts.extend(tags)
    else:
        if isinstance(travel_style, list):
            parts.extend(travel_style)

    if activity_preference:
        parts.append(activity_preference)

    if isinstance(food_preferences, list):
        parts.extend([x for x in food_preferences if str(x).strip().lower() != "no_restrictions"])

    if isinstance(preferred_transport, list):
        parts.extend(preferred_transport)

    if budget_level:
        parts.append(f"budget {budget_level}")

    if pace_preference:
        parts.append(f"pace {pace_preference}")

    if avoid_crowds is True:
        parts.append("avoid crowds")

    if isinstance(rain_preference, str) and rain_preference.strip():
        parts.append(rain_preference)

    cleaned = _clean_parts(parts)
    if not cleaned:
        return "general sightseeing"

    return " | ".join(cleaned)[:400]

def candidate_to_text(c: Dict[str, Any]) -> str:
    """
    Build a richer candidate text representation for CE matching.
    Prioritizes cultural significance, religious importance, and heritage status.
    """
    fields = [
        str(c.get("title") or ""),
        str(c.get("category") or ""),
        str(c.get("description") or ""),
    ]

    # ✅ PRIORITY: Amplify cultural/heritage/religious significance
    significance = c.get("significance") or c.get("importance_level") or ""
    if significance:
        # Repeat for emphasis in CE matching
        fields.append(f"significance: {significance}")

    religion = c.get("religion")
    if religion:
        fields.append(f"religion: {religion}")
        # Add religious keywords for better matching
        if religion.lower() in ["buddhist", "hindu", "christian", "muslim"]:
            fields.append("sacred religious site")

    # ✅ Check if this is a heritage/UNESCO site
    if any(tag in str(c.get("tags", "")).lower() for tag in ["unesco", "heritage", "world heritage"]):
        fields.append("UNESCO World Heritage")

    groups = c.get("groups") or []
    if groups:
        group_str = " ".join(str(g) for g in groups if str(g).strip())
        fields.append(group_str)

    parent = c.get("parent_attraction")
    if parent:
        fields.append(f"part of {parent}")

    # ✅ Add cultural classification tags EARLY
    tags = c.get("tags") or []
    cultural_tags = []
    other_tags = []
    
    if isinstance(tags, list):
        for t in tags:
            t_lower = str(t).lower().strip()
            # Prioritize cultural/heritage themed tags
            if any(keyword in t_lower for keyword in ["cultural", "heritage", "historical", "religious", "spiritual", "archaeological", "temple", "mosque", "church", "shrine", "monastery"]):
                cultural_tags.append(t)
            else:
                other_tags.append(t)
    
    if cultural_tags:
        fields.append("cultural tags: " + " ".join(str(t) for t in cultural_tags))
    
    if other_tags:
        fields.append(" ".join(str(t) for t in other_tags))

    # ✅ Add location context
    fields.append(str(c.get("district") or ""))
    if c.get("city"):
        fields.append(str(c.get("city")))
    if c.get("province"):
        fields.append(str(c.get("province")))

    return " | ".join(x.strip() for x in fields if x and x.strip())


def attach_normalized_ce_scores(candidates: List[Dict[str, Any]]) -> None:
    """
    Convert raw CE logits into 0..1 scores for safe score fusion.
    """
    vals = [float(c.get("_ce_score", 0.0)) for c in candidates if "_ce_score" in c]
    if not vals:
        for c in candidates:
            c["_ce_score_norm"] = 0.0
        return

    lo = min(vals)
    hi = max(vals)

    if abs(hi - lo) < 1e-9:
        for c in candidates:
            c["_ce_score_norm"] = 0.5
        return

    for c in candidates:
        raw = float(c.get("_ce_score", 0.0))
        c["_ce_score_norm"] = (raw - lo) / (hi - lo)


def apply_cultural_priority_boost(candidates: List[Dict[str, Any]], query: str) -> None:
    """
    ✅ NEW: Apply cultural/heritage priority boost after CE scoring.
    If query contains cultural intent, boost religious/heritage sites.
    This corrects CE model bias towards commercial attractions.
    """
    is_cultural_query = any(
        keyword in query.lower()
        for keyword in ["cultural", "heritage", "historical", "religious", "spiritual",
                       "temple", "monastery", "sacred", "archaeological", "spiritual"]
    )
    
    if not is_cultural_query:
        return

    # Apply boost to items with cultural/religious importance
    for c in candidates:
        ce_norm = float(c.get("_ce_score_norm", 0.0))
        
        # Calculate cultural relevance multiplier
        multiplier = 1.0
        
        # High priority: Religious sites with high significance
        category = str(c.get("category", "")).lower()
        religion = str(c.get("religion", "")).lower()
        
        if "religious" in category or "temple" in category or "mosque" in category or "church" in category or "shrine" in category:
            multiplier = 1.25  # +25% boost for religious sites
        elif "monastery" in category:
            multiplier = 1.35  # +35% boost for monasteries (very culturally significant)
        elif "heritage" in category or any(tag in str(c.get("tags", "")).lower() for tag in ["heritage", "historical", "archaeological"]):
            multiplier = 1.15  # +15% boost for heritage sites
        
        # Apply religion boost
        if religion and religion != "none":
            if multiplier == 1.0:  # Only if not already boosted
                multiplier = 1.20
        
        # Apply boost to normalized score
        c["_ce_score_norm"] = min(ce_norm * multiplier, 1.0)


def rerank_candidates_with_cross_encoder(
    *,
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = 20,
    model_name: str = DEFAULT_CE_MODEL,
) -> List[Dict[str, Any]]:
    """
    Rerank top_k candidates with CE.
    Attaches:
      - _ce_text
      - _ce_score       (raw model logit)
      - _ce_score_norm  (0..1 normalized within this batch)
      - _ce_query
    Returns reranked list (highest raw CE first among top_k).
    """
    if not candidates:
        return candidates

    query = str(query or "").strip()
    if not query:
        return candidates

    model = get_cross_encoder(model_name)

    working = list(candidates[:top_k])
    remainder = list(candidates[top_k:])

    pairs = []
    for c in working:
        ce_text = candidate_to_text(c)
        c["_ce_text"] = ce_text
        c["_ce_query"] = query
        pairs.append((query, ce_text))

    scores = model.predict(pairs, batch_size=16, show_progress_bar=False)

    for c, s in zip(working, scores):
        c["_ce_score"] = float(s)

    attach_normalized_ce_scores(working)
    
    # ✅ NEW: Apply cultural priority boost for cultural queries
    apply_cultural_priority_boost(working, query)

    # Sort by normalized CE score (which includes cultural boost if applied)
    working.sort(key=lambda x: float(x.get("_ce_score_norm", 0.0)), reverse=True)
    return working + remainder