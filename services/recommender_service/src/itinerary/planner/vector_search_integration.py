# =============================================================================
# vector_search_integration.py
#
# Drop-in integration for itinerary_planner.py
# Adds preference-aware vector search as a hybrid fetch layer.
#
# HOW IT WORKS:
#   1. fetch_city_attractions_from_kg()  → broad city pool  (existing, unchanged)
#   2. fetch_vector_attractions()        → preference-matched pool (NEW)
#   3. merge_and_boost()                 → deduplicate + boost convergence hits
#   4. Existing enrich_and_rerank + NSGA pipeline runs on merged pool (unchanged)
#
# WHAT CHANGES IN itinerary_planner.py:
#   - In build_itinerary_from_payload(), replace the city-mode KG fetch block
#     with the new hybrid_fetch_city_attractions() call (see bottom of file)
# =============================================================================

from __future__ import annotations
import httpx
import re
from typing import Any, Dict, List, Optional, Tuple
import os

KG_BASE_URL = os.getenv("KG_BASE_URL", "http://localhost:8000").rstrip("/")
KG_VECTOR_SEARCH_PATH = "/sub-attractions/search/vector"

# ---------------------------------------------------------------------------
# STEP 1 — Build a rich semantic query from the payload
# ---------------------------------------------------------------------------

def build_vector_query(payload: Dict[str, Any]) -> str:
    """
    Converts structured payload fields into a natural language semantic query
    for the vector search endpoint.

    Examples:
      payload: {city: "Kandy", travel_style: ["eco-friendly"], raw_text: "I want hiking"}
      → "eco-friendly hiking nature trails Kandy Sri Lanka"

      payload: {city: "Galle", travel_style: ["family"], tags: ["beach", "water sports"]}
      → "family friendly beaches water sports activities Galle Sri Lanka"
    """
    parts: List[str] = []

    # 1. raw_text is the strongest signal — use it directly if present
    raw = (payload.get("raw_text") or "").strip()
    if raw:
        # trim to first 120 chars so query stays focused
        parts.append(raw[:120])

    # 2. travel_style (e.g. ["eco-friendly", "family"])
    styles = payload.get("travel_style") or []
    style_map = {
        "eco-friendly":     "eco nature wildlife conservation",
        "eco friendly":     "eco nature wildlife conservation",
        "eco":              "eco nature trails",
        "family":           "family friendly kids activities",
        "family-friendly":  "family friendly kids activities",
        "cultural":         "cultural heritage temple museum historical",
        "adventure":        "adventure hiking trekking climbing rafting",
        "relaxation":       "peaceful calm scenic relaxing",
        "romantic":         "romantic scenic sunset viewpoint",
        "nature":           "nature wildlife forest parks",
    }
    for s in styles:
        mapped = style_map.get(str(s).strip().lower())
        if mapped:
            parts.append(mapped)
        else:
            parts.append(str(s).strip())

    # 3. tags (e.g. ["beach", "snorkeling"])
    tags = payload.get("tags") or []
    if tags:
        parts.append(" ".join(str(t).strip() for t in tags if t))

    # 4. food_preferences only if no attraction styles present
    if not styles and not tags:
        food = payload.get("food_preferences") or []
        if food:
            parts.append(" ".join(str(f).strip() for f in food if f))

    # 5. Always append city + country for geographic grounding
    #    (city filter param is ignored by endpoint — must be in query)
    city    = (payload.get("city") or payload.get("destination") or "").strip()
    country = (payload.get("country") or "Sri Lanka").strip()
    if city:
        parts.append(city)
    parts.append(country)

    # deduplicate words while preserving order
    seen: set = set()
    words: List[str] = []
    for part in parts:
        for word in part.split():
            w = word.lower()
            if w not in seen:
                seen.add(w)
                words.append(word)

    query = " ".join(words)
    return query


# ---------------------------------------------------------------------------
# STEP 2 — Call the vector search endpoint
# ---------------------------------------------------------------------------

def fetch_vector_attractions(
    payload: Dict[str, Any],
    *,
    limit: int = 40,
    similarity_threshold: float = 0.65,
    timeout: float = 15.0,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Calls /sub-attractions/search/vector with a preference-built query.
    Returns (candidates, debug).

    NOTE: city param is ignored by endpoint → we embed city in the query
    and post-filter by district/province/parentAttraction instead.
    """
    query = build_vector_query(payload)
    city  = (payload.get("city") or payload.get("destination") or "").strip().lower()

    url = f"{KG_BASE_URL}{KG_VECTOR_SEARCH_PATH}"
    params = {
        "query": query,
        "limit": limit,
        "similarity_threshold": similarity_threshold,
    }

    debug: Dict[str, Any] = {
        "vector_url":    url,
        "vector_query":  query,
        "vector_params": params,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, params=params)
            r.raise_for_status()
            data = r.json()

        raw_results: List[Dict[str, Any]] = data.get("results") or []
        debug["vector_raw_count"] = len(raw_results)

        # Deduplicate by googlePlaceId (same POI appears under multiple parentAttractions)
        seen_place_ids: set = set()
        deduped: List[Dict[str, Any]] = []
        for item in raw_results:
            pid = item.get("googlePlaceId") or ""
            if pid and pid in seen_place_ids:
                continue
            seen_place_ids.add(pid)
            deduped.append(item)

        debug["vector_deduped_count"] = len(deduped)

        # Convert to your candidate schema
        candidates = [_vector_item_to_candidate(x) for x in deduped]
        candidates = [c for c in candidates if c]  # drop empty

        # Post-filter: soft city match using district/province/parentAttraction
        # Only filter if we have a city — keeps results broad enough for re-ranking
        if city:
            city_matched   = [c for c in candidates if _vector_city_match(c, city, payload)]
            city_unmatched = [c for c in candidates if not _vector_city_match(c, city, payload)]

            # Always keep city-matched; keep unmatched only if pool is thin
            if len(city_matched) >= 10:
                candidates = city_matched
            else:
                # boost city-matched to top, keep others as fallback
                candidates = city_matched + city_unmatched

        debug["vector_final_count"] = len(candidates)
        debug["ok"] = True
        return candidates, debug

    except Exception as exc:
        debug["error"] = str(exc)
        debug["ok"] = False
        print(f"[VECTOR SEARCH] Error: {exc}")
        return [], debug


# ---------------------------------------------------------------------------
# STEP 3 — Convert vector result → your candidate schema
# ---------------------------------------------------------------------------

def _vector_item_to_candidate(x: Dict[str, Any]) -> Dict[str, Any]:
    """
    Maps vector search result fields to your internal candidate schema.
    Handles the null-heavy fields from the endpoint gracefully.
    """
    name = (x.get("name") or "").strip()
    if not name:
        return {}

    # lat/lng — endpoint uses latitude/longitude
    try:
        lat = float(x["latitude"])  if x.get("latitude")  is not None else None
        lng = float(x["longitude"]) if x.get("longitude") is not None else None
    except (TypeError, ValueError):
        lat, lng = None, None

    # city — often empty string; fall back to parentAttraction
    city = (x.get("city") or "").strip() or (x.get("parentAttraction") or "").strip()

    # district — often null
    district = (x.get("district") or "").strip() or None

    # Generate attraction_id the same way your existing code does
    from services.recommender_service.src.poi.normalize import normalize_to_attraction_id
    attraction_id = normalize_to_attraction_id({
        "title":    name,
        "district": district,
        "city":     city,
        "province": x.get("province"),
        "name":     name,
    })

    return {
        "attraction_id":  attraction_id,
        "google_place_id": x.get("googlePlaceId"),   # store for dedup
        "title":          name,
        "category":       (x.get("category") or "").strip() or "attraction",
        "description":    x.get("description"),
        "city":           city,
        "district":       district,
        "province":       (x.get("province") or "").strip() or None,
        "location":       x.get("vicinity"),
        "rating":         x.get("rating"),
        "lat":            lat,
        "lng":            lng,
        "parent_attraction": x.get("parentAttraction"),
        "source":         "vector_search",
        # Vector similarity score → used as _score input
        "_score":         float(x.get("similarity") or 0.0),
        "_vector_sim":    float(x.get("similarity") or 0.0),
        # Pre-seed eco hint so enrich pipeline works
        "_eco_hint":      _infer_eco_hint(x),
    }


def _infer_eco_hint(x: Dict[str, Any]) -> float:
    """Quick eco signal from category + description for vector results."""
    blob = " ".join([
        str(x.get("name") or ""),
        str(x.get("description") or ""),
        str(x.get("category") or ""),
        str(x.get("parentAttraction") or ""),
    ]).lower()
    eco_hits = ["eco", "forest", "nature", "park", "reserve", "sanctuary",
                "wildlife", "trail", "hike", "lake", "botanical", "waterfall"]
    bad_hits = ["mall", "casino", "restaurant", "hotel", "resort"]
    score = 0.5
    for w in eco_hits:
        if w in blob:
            score += 0.07
    for w in bad_hits:
        if w in blob:
            score -= 0.15
    return max(0.0, min(1.0, score))


def _vector_city_match(c: Dict[str, Any], city: str, payload: Dict[str, Any]) -> bool:
    """
    Soft city match for vector results.
    Checks district, province, city, parentAttraction fields.
    Since city is often empty in vector results, we're intentionally lenient.
    """
    city_l = city.strip().lower()
    if not city_l:
        return True

    # Known city → district/province mappings for Sri Lanka
    # Extend this as needed
    city_region_map: Dict[str, List[str]] = {
        "kandy":        ["kandy", "central", "matale", "nuwara eliya"],
        "colombo":      ["colombo", "western", "gampaha", "kalutara"],
        "galle":        ["galle", "southern", "matara", "hambantota"],
        "ella":         ["badulla", "uva", "ella"],
        "sigiriya":     ["matale", "central", "sigiriya", "dambulla"],
        "anuradhapura": ["anuradhapura", "north central"],
        "polonnaruwa":  ["polonnaruwa", "north central"],
        "trincomalee":  ["trincomalee", "eastern"],
        "jaffna":       ["jaffna", "northern"],
        "mirissa":      ["matara", "southern"],
        "hikkaduwa":    ["galle", "southern"],
        "bentota":      ["kalutara", "western", "bentota"],
        "nuwara eliya": ["nuwara eliya", "central"],
        "arugam bay":   ["ampara", "eastern", "arugambay"],
        "yala":         ["hambantota", "southern", "yala"],
    }

    allowed_regions = city_region_map.get(city_l, [city_l])

    for field in ("city", "district", "province", "parent_attraction"):
        val = str(c.get(field) or "").strip().lower()
        if not val:
            continue
        for region in allowed_regions:
            if region in val or val in region:
                return True

    return False


# ---------------------------------------------------------------------------
# STEP 4 — Merge city pool + vector pool with convergence boost
# ---------------------------------------------------------------------------

def merge_and_boost(
    city_candidates:   List[Dict[str, Any]],
    vector_candidates: List[Dict[str, Any]],
    *,
    convergence_boost: float = 0.25,
    vector_sim_weight: float = 0.40,
) -> List[Dict[str, Any]]:
    """
    Merges two candidate pools and boosts items that appear in BOTH.

    Convergence boost logic:
      - Item in BOTH pools  → gets +convergence_boost on top of vector_sim score
        (it's geographically relevant AND semantically matched)
      - Item only in vector → gets vector_sim_weight * similarity added to score
      - Item only in city   → score unchanged (existing pipeline handles it)

    This means: if you change preferences from "eco hiking" to "family beaches",
    the TOP of the merged pool will be different because vector results are different.
    """
    # Index city candidates by attraction_id and google_place_id
    city_by_aid:  Dict[str, Dict] = {}
    city_by_gpid: Dict[str, Dict] = {}

    for c in city_candidates:
        aid  = c.get("attraction_id") or ""
        gpid = c.get("google_place_id") or ""
        if aid:
            city_by_aid[aid]   = c
        if gpid:
            city_by_gpid[gpid] = c

    merged: Dict[str, Dict[str, Any]] = {}

    # 1. Start with all city candidates as base
    for c in city_candidates:
        key = c.get("attraction_id") or c.get("google_place_id") or c.get("title", "")
        merged[key] = c
        c["_in_city_pool"]  = True
        c["_in_vector_pool"] = False

    # 2. Process vector candidates
    for v in vector_candidates:
        v_aid  = v.get("attraction_id") or ""
        v_gpid = v.get("google_place_id") or ""
        v_sim  = float(v.get("_vector_sim") or 0.0)

        # Check if this vector result already exists in city pool
        existing = city_by_aid.get(v_aid) or city_by_gpid.get(v_gpid)

        if existing:
            # ✅ CONVERGENCE: item is in BOTH pools → boost it
            existing["_in_vector_pool"] = True
            existing["_vector_sim"]     = v_sim
            existing["_convergence"]    = True

            base_score = float(existing.get("_score") or 0.0)
            existing["_score"] = base_score + convergence_boost + (vector_sim_weight * v_sim)
            existing["_boost_reason"] = "convergence: city + vector match"
        else:
            # ✅ VECTOR ONLY: preference-matched but not in city pool
            # Add with vector similarity as score
            v["_in_city_pool"]   = False
            v["_in_vector_pool"] = True
            v["_convergence"]    = False
            v["_score"] = vector_sim_weight * v_sim
            v["_boost_reason"] = "vector_only: preference match"

            key = v_aid or v_gpid or v.get("title", "")
            if key and key not in merged:
                merged[key] = v

    result = list(merged.values())

    # Sort by score descending so best candidates bubble to top before re-ranking
    result.sort(key=lambda x: float(x.get("_score") or 0.0), reverse=True)

    return result


# ---------------------------------------------------------------------------
# STEP 5 — Hybrid fetch (replaces fetch_city_attractions_from_kg in city mode)
# ---------------------------------------------------------------------------

def hybrid_fetch_city_attractions(
    payload:  Dict[str, Any],
    city:     str,
    country:  str,
    limit:    int = 60,
    *,
    vector_limit:      int   = 40,
    vector_threshold:  float = 0.65,
    convergence_boost: float = 0.25,
    vector_sim_weight: float = 0.40,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    from .itinerary_planner import fetch_city_attractions_from_kg

    city_candidates = []
    city_dbg = {
        "ok": False,
        "error": None,
        "kg_returned": 0,
        "candidates_returned": 0,
    }

    try:
        city_candidates, city_dbg = fetch_city_attractions_from_kg(
            city=city,
            country=country,
            limit=limit,
            timeout=40.0,
        )
    except Exception as exc:
        city_dbg = {
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "kg_returned": 0,
            "candidates_returned": 0,
        }
        print(f"[HYBRID FETCH] city KG fetch failed for city='{city}': {exc}")

    vector_candidates, vector_dbg = fetch_vector_attractions(
        payload=payload,
        limit=vector_limit,
        similarity_threshold=vector_threshold,
    )

    merged = merge_and_boost(
        city_candidates=city_candidates,
        vector_candidates=vector_candidates,
        convergence_boost=convergence_boost,
        vector_sim_weight=vector_sim_weight,
    )

    n_converged = sum(1 for c in merged if c.get("_convergence"))
    n_vector_only = sum(1 for c in merged if c.get("_in_vector_pool") and not c.get("_convergence"))
    n_city_only = sum(1 for c in merged if c.get("_in_city_pool") and not c.get("_in_vector_pool"))

    debug = {
        **city_dbg,
        "vector_search": vector_dbg,
        "hybrid": {
            "city_pool_size": len(city_candidates),
            "vector_pool_size": len(vector_candidates),
            "merged_pool_size": len(merged),
            "convergence_hits": n_converged,
            "vector_only": n_vector_only,
            "city_only": n_city_only,
            "query_used": vector_dbg.get("vector_query"),
        },
    }

    print(f"\n[HYBRID FETCH] city={city}")
    print(f"  city_pool={len(city_candidates)} | vector_pool={len(vector_candidates)} | merged={len(merged)}")
    print(f"  convergence_hits={n_converged} | vector_only={n_vector_only} | city_only={n_city_only}")
    print(f"  query: {vector_dbg.get('vector_query', '')[:80]}...")

    return merged, debug