from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
import json
from pathlib import Path
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional
from pathlib import Path
from services.recommender_service.src.itinerary.json_kg import query_attractions_from_json
from services.recommender_service.src.itinerary.enrichment.enrich_candidates import (
    enrich_and_rerank_candidates,
    EnrichConfig,
)
from ..enrichment.enrich_candidates import enrich_and_rerank_candidates
from ..nsga.objectives import build_objectives
from ..nsga.pareto import pareto_front
from ..json_kg import query_attractions_from_json
from ..ranking.corridor import query_attractions_along_route





from services.recommender_service.src.poi.normalize import (
    normalize_to_attraction_id,
    get_attraction_record,
)
from services.recommender_service.src.itinerary.enrichment.enrich_item import enrich_attraction


def _find_repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / "data").exists() and (parent / "services").exists():
            return parent
    # fallback (safe-ish)
    return p.parents[5]


def _load_attractions() -> List[Dict[str, Any]]:
    repo_root = _find_repo_root()
    path = repo_root / "data" / "recommender_service" / "clean" / "kg" / "attractions_clean.json"
    raw = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(raw, dict) and isinstance(raw.get("attractions"), list):
        return [x for x in raw["attractions"] if isinstance(x, dict)]
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    return []


def _load_restaurants_optional() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    repo_root = _find_repo_root()
    path = repo_root / "data" / "recommender_service" / "clean" / "kg" / "restaurants_clean.json"
    if not path.exists():
        return [], f"restaurants_clean.json not found at {path} (restaurants omitted)"
    raw = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(raw, dict) and isinstance(raw.get("restaurants"), list):
        return [x for x in raw["restaurants"] if isinstance(x, dict)], None
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)], None
    return [], "restaurants_clean.json schema not recognized; restaurants omitted"


def _safe_city_match(rec: Dict[str, Any], city: str) -> bool:
    city_l = (city or "").strip().lower()
    if not city_l:
        return True
    for k in ("city", "district", "province", "location"):
        v = str(rec.get(k) or "").strip().lower()
        if v and city_l in v:
            return True
    return False


def _eco_score_hint(rec: Dict[str, Any]) -> float:
    text = " ".join(
        [str(rec.get(k) or "") for k in ("tags", "category", "type", "title", "name", "description")]
    ).lower()
    eco_hits = ["eco", "forest", "nature", "park", "reserve", "botanical", "lake", "hike", "trail", "sanctuary"]
    bad_hits = ["mall", "casino", "nightclub"]
    score = 0.5
    for w in eco_hits:
        if w in text:
            score += 0.07
    for w in bad_hits:
        if w in text:
            score -= 0.15
    return max(0.0, min(1.0, score))


# def _estimate_cost_lkr(item: Dict[str, Any], kind: str) -> int:
#     for k in ("estimated_cost_lkr", "cost_lkr", "price_lkr", "avg_cost_lkr"):
#         if item.get(k) is not None:
#             try:
#                 v = int(float(item[k]))
#                 if v > 0:
#                     return v
#             except Exception:
#                 pass
#     return 3000 if kind == "restaurant" else 5000


def _veg_ok(restaurant: Dict[str, Any]) -> bool:
    text = " ".join(
        [str(restaurant.get(k) or "") for k in ("diet", "diet_options", "tags", "cuisine", "menu", "description", "name", "title")]
    ).lower()
    return ("vegetarian" in text) or ("vegan" in text) or ("veg " in text)


@dataclass
class PlannerConfig:
    per_day_attractions: int = 2   # morning + afternoon
    meals_per_day: int = 1         # dinner only
    max_candidates: int = 60

# ----------------------------
# Dynamic priority extraction
# ----------------------------

@dataclass
class Priority:
    key: str                # canonical key e.g. "eco-friendly"
    weight: float           # higher means more important
    source: str             # "raw_text" | "structured"
    matched_phrase: str     # what matched in text


def _normalize_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _compile_priority_vocab() -> List[Tuple[str, List[str]]]:
    """
    Canonical key -> list of phrases/synonyms.
    Extend this anytime; this is not "hardcoding priorities", it is the system vocabulary.
    """
    return [
        ("eco-friendly", ["eco-friendly", "eco friendly", "eco", "nature", "green", "sustainable", "wildlife", "forest", "park", "reserve", "botanical"]),
        ("family-friendly", ["family-friendly", "family friendly", "kids", "child-friendly", "child friendly", "family"]),
        ("cultural", ["cultural", "heritage", "temple", "museum", "historical", "history"]),
        ("adventure", ["adventure", "hiking", "trek", "trail", "climb", "rafting", "surf", "diving"]),
        ("relaxation", ["relax", "relaxing", "chill", "quiet", "calm", "spa"]),
        ("romantic", ["romantic", "honeymoon", "couples"]),
        ("avoid_crowds", ["avoid crowds", "less crowded", "not crowded", "crowd-free", "crowd free", "avoid busy"]),
        ("avoid_rain", ["avoid rain", "no rain", "less rain", "dry weather", "dry"]),
        ("budget", ["under", "budget", "cheap", "affordable", "low cost", "mid budget", "luxury"]),
        ("vegetarian", ["vegetarian", "veg only", "veg-only", "vegan"]),
        ("halal", ["halal"]),
    ]


def extract_priorities(payload: Dict[str, Any]) -> List[Priority]:
    """
    1) Use raw_text ordering (most important).
    2) Fallback to structured fields (travel_style, tags, etc.) if raw_text missing.
    Returns priorities in descending weight.
    """
    raw = _normalize_text(str(payload.get("raw_text") or ""))
    vocab = _compile_priority_vocab()

    found: List[Tuple[int, str, str]] = []  # (position, key, matched_phrase)

    if raw:
        # find earliest position for each canonical key
        for key, phrases in vocab:
            best_pos = None
            best_phrase = None
            for ph in phrases:
                ph_n = _normalize_text(ph)
                # word boundary-ish match
                m = re.search(rf"(?<!\w){re.escape(ph_n)}(?!\w)", raw)
                if m:
                    pos = m.start()
                    if best_pos is None or pos < best_pos:
                        best_pos = pos
                        best_phrase = ph
            if best_pos is not None:
                found.append((best_pos, key, best_phrase or key))

        # sort by appearance order in query
        found.sort(key=lambda x: x[0])

        # convert ordered keys into decreasing weights
        # first mentioned gets highest weight, next slightly less, etc.
        priorities: List[Priority] = []
        base = 1.0
        decay = 0.12  # controls how fast priority importance drops
        for idx, (_pos, key, phrase) in enumerate(found):
            w = max(0.25, base - idx * decay)
            priorities.append(Priority(key=key, weight=w, source="raw_text", matched_phrase=phrase))
        return priorities

    # ---- structured fallback (no raw_text) ----
    structured_keys: List[str] = []
    for field in ("travel_style", "tags", "food_preferences"):
        v = payload.get(field)
        if isinstance(v, list):
            structured_keys.extend([_normalize_text(str(x)) for x in v if x])

    priorities: List[Priority] = []
    # map structured to canonical keys by synonym matching
    for idx, item in enumerate(structured_keys):
        for key, phrases in vocab:
            if any(item == _normalize_text(p) for p in phrases) or item == _normalize_text(key):
                # earlier items get higher weight
                w = max(0.25, 0.8 - idx * 0.08)
                priorities.append(Priority(key=key, weight=w, source="structured", matched_phrase=item))
                break

    # de-duplicate keeping highest weight
    best: Dict[str, Priority] = {}
    for p in priorities:
        if p.key not in best or p.weight > best[p.key].weight:
            best[p.key] = p

    out = list(best.values())
    out.sort(key=lambda p: p.weight, reverse=True)
    return out


# ----------------------------
# Dynamic candidate scoring
# ----------------------------

def _text_blob(rec: Dict[str, Any]) -> str:
    return _normalize_text(" ".join([
        str(rec.get("title") or rec.get("name") or ""),
        str(rec.get("category") or ""),
        str(rec.get("type") or ""),
        str(rec.get("tags") or ""),
        str(rec.get("description") or ""),
        str(rec.get("province") or ""),
        str(rec.get("district") or ""),
        str(rec.get("city") or ""),
    ]))


def _matches_priority(rec: Dict[str, Any], priority_key: str) -> float:
    """
    Return 0..1 relevance for how well this attraction matches a priority.
    Keep it simple and conservative.
    """
    blob = _text_blob(rec)

    if priority_key == "eco-friendly":
        hits = ["eco", "nature", "forest", "park", "reserve", "botanical", "lake", "sanctuary", "trail", "hike", "wildlife"]
        return 1.0 if any(h in blob for h in hits) else 0.0

    if priority_key == "family-friendly":
        hits = ["family", "kids", "child", "park", "garden", "lake", "walk"]
        return 1.0 if any(h in blob for h in hits) else 0.0

    if priority_key == "cultural":
        hits = ["temple", "museum", "heritage", "historical", "sacred", "church", "kovil"]
        return 1.0 if any(h in blob for h in hits) else 0.0

    if priority_key == "adventure":
        hits = ["hike", "trail", "trek", "climb", "rafting", "surf", "dive", "adventure"]
        return 1.0 if any(h in blob for h in hits) else 0.0

    if priority_key == "relaxation":
        hits = ["relax", "calm", "quiet", "lake", "garden", "walk", "viewpoint"]
        return 1.0 if any(h in blob for h in hits) else 0.0

    if priority_key == "romantic":
        hits = ["romantic", "sunset", "viewpoint", "lake", "garden"]
        return 1.0 if any(h in blob for h in hits) else 0.0

    # these are constraints; they should be handled elsewhere
    if priority_key in ("avoid_crowds", "avoid_rain", "budget", "vegetarian", "halal"):
        return 0.0

    return 0.0


def compute_rank_score(
    rec: Dict[str, Any],
    priorities: List[Priority],
    eco_preference: float,
) -> float:
    """
    Rank score is a weighted sum of:
    - query priorities (ordered)
    - eco_hint (still useful, but not hardcoded as "sort by eco")
    """
    # baseline from eco_hint (0..1)
    eco_hint = float(rec.get("_eco_hint", 0.5))
    score = 0.25 * eco_hint + 0.05 * float(eco_preference)  # light baseline

    # priority contributions
    for p in priorities:
        rel = _matches_priority(rec, p.key)  # 0..1
        score += p.weight * rel

    return float(score)


# def build_itinerary_from_payload(payload: Dict[str, Any], cfg: PlannerConfig = PlannerConfig()) -> Dict[str, Any]:
#     city = str(payload.get("city") or payload.get("destination") or "").strip() or "Colombo"
#     country = str(payload.get("country") or "Sri Lanka").strip() or "Sri Lanka"
#     eco_pref = float(payload.get("eco_preference") or 0.5)
#     days = int(payload.get("days") or 3)

#     start_str = str(payload.get("start_date") or "").strip()
#     if not start_str:
#         raise ValueError("payload.start_date required (YYYY-MM-DD)")

#     y, m, d = [int(x) for x in start_str.split("-")]
#     start_dt = date(y, m, d)

#     warnings: List[str] = []

#     res = query_attractions_from_json(
#         payload,
#         kg_path=Path("/Users/dev/Desktop/graphCeylon-API/data/recommender_service/clean/kg/attractions_clean.json"),
#         limit=int(payload.get("max_candidates", cfg.max_candidates)),
#         prefilter_limit=300,
#     )
#     dbg = getattr(res, "debug", None) or {}

#     print("\n================ JSON-KG QUERY OUTPUT =================")

#     print("\n--- Debug Keys ---")
#     print(list(dbg.keys()))

#     print("\n--- Extracted Priorities ---")
#     for p in dbg.get("priorities", []):
#         print(f"{p.get('key')} | w={p.get('weight')} | src={p.get('source')} | phrase={p.get('matched_phrase')}")

#     print("\n--- Preference Source Map ---")
#     pref_src = dbg.get("preference_sources") or dbg.get("trace", {}).get("preference_sources") or {}
#     for k, v in pref_src.items():
#         print(f"{k:25s} -> {v}")

#     print("\n--- Top Ranked Attractions ---")
#     for a in (getattr(res, "candidates", []) or [])[:10]:
#         print(f"{a.get('title','?'):<25} | score={a.get('_rank_score', 0):.3f} | eco={a.get('_eco_hint', 0):.2f}")

#     print("=======================================================\n")



    

#     norm_atts = res.candidates  # already ranked
#     if not norm_atts:
#         warnings.append(f"No attractions found for city='{city}'.")



#     itinerary_days: List[Dict[str, Any]] = []
#     used_attractions: set[str] = set()

#     for i in range(days):
#         day_date = start_dt + timedelta(days=i)
#         day_str = day_date.isoformat()
#         day_items: List[Dict[str, Any]] = []

#         # select attractions for day
#         selected_atts: List[Dict[str, Any]] = []
#         for a in norm_atts:
#             aid = str(a.get("attraction_id") or "").strip()
#             if not aid or aid in used_attractions:
#                 continue
#             selected_atts.append(a)
#             used_attractions.add(aid)
#             if len(selected_atts) >= cfg.per_day_attractions:
#                 break

#         slots = ["morning", "afternoon"]
#         for idx, a in enumerate(selected_atts):
#             aid = a["attraction_id"]

#             enrich = enrich_attraction(
#                 attraction_id=aid,
#                 date_str=day_str,
#                 eco_preference=eco_pref,
#                 country=country,
#                 explicit_city=city,
#             )

#             day_items.append({
#                 "slot": slots[idx] if idx < len(slots) else f"slot_{idx+1}",
#                 "kind": "attraction",
#                 "attraction_id": aid,
#                 "title": a.get("title") or a.get("name"),
#                 "district": a.get("district"),
#                 "city": a.get("city") or city,

#                 # 🔢 why this was chosen before others
#                 "rank_score": float(a.get("_rank_score", 0.0)),

#                 "enrichment": enrich,
#                 "raw": {k: v for k, v in a.items() if not str(k).startswith("_")},
#             })

#         itinerary_days.append({
#             "date": day_str,
#             "city": city,
#             "items": day_items,
#         })

#     return {
#         "status": "ok",
#         "city": city,
#         "country": country,
#         "start_date": start_dt.isoformat(),
#         "days": days,

#         # 🔎 show what the system extracted from this query
#         "priorities": [
#             {
#                 "key": p.key,
#                 "weight": p.weight,
#                 "source": p.source,
#                 "matched_phrase": p.matched_phrase,
#             }
#             for p in priorities
#         ],

#         "preferences_used": {
#             "eco_preference": eco_pref,
#             "travel_style": payload.get("travel_style"),
#             "food_preferences": payload.get("food_preferences"),
#             "budget_level": payload.get("budget_level"),
#             "accommodation_type": payload.get("accommodation_type"),
#         },
#         "warnings": warnings,
#         "itinerary": itinerary_days,
#     }
from collections import defaultdict

def group_by_district(candidates):
    buckets = defaultdict(list)
    for p in candidates:
        d = p.get("district") or p.get("city") or "unknown"
        buckets[d].append(p)

    for d in buckets:
        buckets[d].sort(key=lambda x: x.get("_final_score", x.get("_score", 0.0)), reverse=True)

    return buckets


def district_centroid(pois):
    lats = [p["lat"] for p in pois if p.get("lat") is not None]
    lngs = [p["lng"] for p in pois if p.get("lng") is not None]
    if not lats or not lngs:
        return None
    return (sum(lats) / len(lats), sum(lngs) / len(lngs))


def order_districts(buckets, anchor):
    # ✅ if no anchor, just keep bucket order
    if not anchor:
        return list(buckets.keys())

    ax, ay = anchor
    centroids = []
    for d, pois in buckets.items():
        c = district_centroid(pois)
        if c is None:
            continue
        centroids.append((d, c))

    centroids.sort(key=lambda x: (x[1][0] - ax) ** 2 + (x[1][1] - ay) ** 2)
    return [d for d, _ in centroids]


def build_itinerary(ranked_candidates, days, per_day=2, anchor=None):
    buckets = group_by_district(ranked_candidates)
    ordered_districts = order_districts(buckets, anchor)

    itinerary = []
    used = set()

    for day in range(days):
        if not ordered_districts:
            break

        district = ordered_districts.pop(0)
        pois = buckets[district]

        day_plan = []
        for p in pois:
            aid = p.get("attraction_id")
            if not aid:
                continue
            if aid not in used:
                day_plan.append(p)
                used.add(aid)
            if len(day_plan) >= per_day:
                break

        itinerary.append({
            "day": day + 1,
            "district": district,
            "attractions": day_plan
        })

    return itinerary

def build_itinerary_from_payload(payload: Dict[str, Any], cfg: PlannerConfig = PlannerConfig()) -> Dict[str, Any]:
    city = str(payload.get("city") or payload.get("destination") or "").strip() or "Colombo"
    country = str(payload.get("country") or "Sri Lanka").strip() or "Sri Lanka"
    eco_pref = float(payload.get("eco_preference") or 0.5)
    days = int(payload.get("days") or 3)

    start_str = str(payload.get("start_date") or "").strip()
    if not start_str:
        raise ValueError("payload.start_date required (YYYY-MM-DD)")

    y, m, d = [int(x) for x in start_str.split("-")]
    start_dt = date(y, m, d)

    warnings: List[str] = []

    # ✅ call your JSON-KG query
    res = query_attractions_from_json(
        payload,
        kg_path=Path("/Users/dev/Desktop/graphCeylon-API/data/recommender_service/clean/kg/attractions_clean.json"),
        #kg_path=Path("C:/Users/HP/OneDrive/Documents/graphCeylon-API/data/recommender_service/clean/kg/attractions_clean.json"),
        limit=int(payload.get("max_candidates", cfg.max_candidates)),
        prefilter_limit=300,
    )

    # ✅ debug dict (safe)
    dbg = getattr(res, "debug", None) or {}

    # ✅ FIX: ensure `priorities` exists in THIS scope (Priority objects)
    priorities: List[Priority] = extract_priorities(payload) or []

    # ✅ OPTIONAL: keep dbg priorities in sync (dict form) so printing always works
    dbg["priorities"] = [
        {"key": p.key, "weight": p.weight, "source": p.source, "matched_phrase": p.matched_phrase}
        for p in priorities
    ]

    # ---------------- DEBUG PRINTS ----------------
    print("\n================ JSON-KG QUERY OUTPUT =================")

    print("\n--- Debug Keys ---")
    print(list(dbg.keys()))

    print("\n--- Extracted Priorities ---")
    for p in dbg.get("priorities", []):
        print(f"{p.get('key')} | w={p.get('weight')} | src={p.get('source')} | phrase={p.get('matched_phrase')}")

    print("\n--- Preference Source Map ---")
    pref_src = (
        dbg.get("preference_sources")
        or dbg.get("trace", {}).get("preference_sources")
        or payload.get("trace", {}).get("preference_sources")
        or {}
    )
    for k, v in pref_src.items():
        print(f"{k:25s} -> {v}")

    print("\n--- Top Ranked Attractions ---")
    for a in (getattr(res, "candidates", []) or [])[:10]:
        feat = a.get("_features", {}) or {}
        print(
            f"{a.get('title','?'):<25} | score={a.get('_score', 0.0):.3f} | "
            f"eco={feat.get('eco_hint', 0.0):.2f} | prox={feat.get('proximity', 0.0):.2f}"
        )

    print("=======================================================\n")
    # -----------------------------------------------------

    # ✅ candidates already ranked by your query function
    kg_atts = getattr(res, "candidates", None) or []

    # Print old KG top-10
    print("\n--- Top KG Ranked Attractions (base _score) ---")
    for a in kg_atts[:10]:
        feat = a.get("_features", {}) or {}
        print(
            f"{a.get('title','?'):<25} | base={a.get('_score', 0.0):.3f} | "
            f"eco={feat.get('eco_hint', 0.0):.2f} | prox={feat.get('proximity', 0.0):.2f}"
        )

    # ✅ dynamic enrichment + reranking (adds _final_score + _dynamic + _enrichment)
    reranked = enrich_and_rerank_candidates(
        candidates=kg_atts,
        payload=payload,
        cfg=EnrichConfig(
            w_sustainability=1.2,
            w_crowd_avoid=0.8,
            w_rain_avoid=0.6,
        ),
        day_offset=0,  # rerank using start_date day (day 0)
    )

    # Print new reranked top-10
    print("\n--- Top Reranked Attractions (base + dynamic) ---")
    for a in reranked[:10]:
        dyn = a.get("_dynamic", {}) or {}
        base = float(a.get("_score", 0.0))
        final = float(a.get("_final_score", 0.0))
        print(
            f"{a.get('title','?'):<25} | final={final:.3f} | base={base:.3f} | "
            f"sus={float(dyn.get('sustainability_0_1', 0.0)):.2f} | "
            f"crowd={float(dyn.get('crowd_risk_0_1', 0.0)):.2f} | "
            f"rain={float(dyn.get('rain_risk_0_1', 0.0)):.2f}"
        )
    # ================= NSGA-II PARETO SELECTION =================

    obj_vectors = []
    for i, cand in enumerate(reranked):
        objectives, explain = build_objectives(cand, payload)
        cand["_nsga_objectives"] = objectives
        cand["_nsga_explain"] = explain
        obj_vectors.append((objectives, i))

    front_indices = pareto_front(obj_vectors)

    pareto_candidates = [reranked[i] for i in front_indices]

    print("\n--- NSGA-II Pareto Front (multi-objective optimal set) ---")
    for c in pareto_candidates[:10]:
        e = c["_nsga_explain"]
        print(
            f"{c.get('title','?'):<25} | "
            f"match={e['match_0_1']:.2f} sus={e['sustainability_0_1']:.2f} "
            f"crowd={e['crowd_risk_0_1']:.2f} rain={e['rain_risk_0_1']:.2f}"
        )

    # ✅ use reranked list for planning
    norm_atts = pareto_candidates


    if not norm_atts:
        warnings.append(f"No attractions found for city='{city}'.")

    # ✅ days and per_day must come from user payload (not hardcoded)
    days = int(payload.get("days") or 1)
    per_day = int(payload.get("per_day_attractions") or cfg.per_day_attractions)

    # ✅ get anchor coords if your JSON-KG query stored it in debug
    anchor = None
    if isinstance(dbg, dict):
        anchor = dbg.get("anchor_coords") or dbg.get("anchor")  # whichever you store

    # ✅ build a day-wise district-rotating plan
    simple_itinerary = build_itinerary(
        ranked_candidates=norm_atts,
        days=days,
        per_day=per_day,
        anchor=anchor,
    )

    # ✅ convert to your response format (date/slots + enrichment)
    itinerary_days: List[Dict[str, Any]] = []
    slots = ["morning", "afternoon", "evening", "night"]

    for i, day_pack in enumerate(simple_itinerary):
        day_date = start_dt + timedelta(days=i)
        day_str = day_date.isoformat()

        day_items: List[Dict[str, Any]] = []
        for idx, a in enumerate(day_pack["attractions"]):
            aid = a["attraction_id"]

            enrich = a.get("_enrichment") or enrich_attraction(
                attraction_id=aid,
                date_str=day_str,
                eco_preference=eco_pref,
                country=country,
                explicit_city=city,
            )

            day_items.append({
                "slot": slots[idx] if idx < len(slots) else f"slot_{idx+1}",
                "kind": "attraction",
                "attraction_id": aid,
                "title": a.get("title") or a.get("name"),
                "district": a.get("district"),
                "city": a.get("city") or city,
                "rank_score_base": float(a.get("_score", 0.0)),
                "rank_score_final": float(a.get("_final_score", a.get("_score", 0.0))),
                "dynamic": a.get("_dynamic", {}),
                "enrichment": enrich,
                "raw": {k: v for k, v in a.items() if not str(k).startswith("_")},
            })

        itinerary_days.append({
            "date": day_str,
            "city": city,
            "district": day_pack.get("district"),
            "items": day_items
        })


    return {
        "status": "ok",
        "city": city,
        "country": country,
        "start_date": start_dt.isoformat(),
        "days": days,
        "priorities": [
            {"key": p.key, "weight": p.weight, "source": p.source, "matched_phrase": p.matched_phrase}
            for p in priorities
        ],
        "preferences_used": {
            "eco_preference": eco_pref,
            "travel_style": payload.get("travel_style"),
            "food_preferences": payload.get("food_preferences"),
            "budget_level": payload.get("budget_level"),
            "accommodation_type": payload.get("accommodation_type"),
        },
        "warnings": warnings,
        "itinerary": itinerary_days,
    }