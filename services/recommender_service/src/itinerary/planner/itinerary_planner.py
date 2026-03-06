from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
import json
import re
import copy
from pathlib import Path
import math
from ..enrichment.enrich_candidates import enrich_and_rerank_candidates, EnrichConfig
from ..enrichment.enrich_item import enrich_attraction
from ..nsga.objectives import build_objectives
from ..nsga.pareto import pareto_front
from .resolve_travel_mode import resolve_travel_mode
from .gate import needs_clarification
from .city_planner import get_candidates_city
from .corridor_planner import get_candidates_corridor
import os
import httpx
from copy import deepcopy
from typing import Literal
PlanMode = Literal["city", "corridor_outbound", "corridor_return"]
#from services.recommender_service.src.routing.graphhopper_route import fetch_route_sampled_points
from services.recommender_service.src.routing.city_coords import resolve_city_coords
from services.recommender_service.src.routing.graphhopper_route import fetch_route_sampled_points
from services.recommender_service.src.poi.normalize import (
    normalize_to_attraction_id,
    get_attraction_record,
)
from services.recommender_service.src.itinerary.enrichment.enrich_item import enrich_attraction
#from services.recommender_service.src.routing.city_coords1 import resolve_city_coords
from collections import defaultdict
from .semantic_ranker import attach_semantic_scores
from .semantic_ranker import build_semantic_query  # new helper
def _find_repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / "data").exists() and (parent / "services").exists():
            return parent
    # fallback (safe-ish)
    return p.parents[5]
def _cities_json_path() -> Path:
    repo_root = _find_repo_root()
    return repo_root / "services" / "recommender_service" / "src" / "routing" / "cities.json"
def _is_destination_candidate(c: Dict[str, Any], dest_city: str) -> bool:
    dc = (dest_city or "").strip().lower()
    if not dc:
        return True
    # your KG uses district heavily; sometimes city is present too
    cand_city = str(c.get("city") or "").strip().lower()
    cand_dist = str(c.get("district") or "").strip().lower()
    return (cand_city == dc) or (cand_dist == dc) or (dc in cand_city) or (dc in cand_dist)
def _is_destination_area(c: Dict[str, Any], dest_city: str) -> bool:
    dc = (dest_city or "").strip().lower()
    if not dc:
        return False
    cand_city = str(c.get("city") or "").strip().lower()
    cand_dist = str(c.get("district") or "").strip().lower()
    return (cand_city == dc) or (cand_dist == dc) or (dc in cand_city) or (dc in cand_dist)
def build_route_day_only(route_candidates, per_day_limit: int, day_number: int):
    picked = []
    used = set()
    for c in route_candidates:
        aid = c.get("attraction_id")
        if not aid or aid in used:
            continue
        picked.append(c)
        used.add(aid)
        if len(picked) >= per_day_limit:
            break
    return [{
        "day": day_number,
        "district": picked[0].get("district") if picked else None,
        "attractions": picked
    }]
def _haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlat/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(x))
def attach_nearest_route_point(route_candidates: List[Dict[str, Any]], sampled_points: List[Tuple[float, float]]):
    """
    For each attraction, find the nearest downsampled route point.
    Saves:
      _nearest_point_index
      _nearest_point_km
      _nearest_point (lat, lon)
    """
    if not sampled_points:
        return
    for c in route_candidates:
        lat = c.get("lat")
        lng = c.get("lng")
        if lat is None or lng is None:
            c["_nearest_point_index"] = None
            c["_nearest_point_km"] = None
            continue
        try:
            p = (float(lat), float(lng))
        except Exception:
            c["_nearest_point_index"] = None
            c["_nearest_point_km"] = None
            continue
        best_i = None
        best_d = 10**9
        # brute-force is fine because sampled_points are downsampled (usually ~20-60)
        for i, sp in enumerate(sampled_points):
            d = _haversine_km(p, sp)
            if d < best_d:
                best_d = d
                best_i = i
        c["_nearest_point_index"] = best_i
        c["_nearest_point_km"] = float(best_d)
        c["_nearest_point"] = sampled_points[best_i] if best_i is not None else None
def build_route_by_district(route_candidates: List[Dict[str, Any]], *, per_district: int = 2, max_districts: int = 10):
    """
    Returns a multi-district route stop list (NOT destination district),
    ordered by first appearance along the route (route_point_index).
    """
    # group by district and track earliest route index
    buckets = defaultdict(list)
    first_idx = {}
    for c in route_candidates:
        dist = (c.get("district") or c.get("city") or "unknown").strip()
        rpi = c.get("_nearest_point_index") or c.get("_route_point_index")
        if rpi is None:
            continue
        buckets[dist].append(c)
        first_idx[dist] = min(first_idx.get(dist, 10**9), int(rpi))
    # order districts by appearance on the route
    ordered_districts = sorted(first_idx.keys(), key=lambda d: first_idx[d])
    out = []
    for dist in ordered_districts[:max_districts]:
        pois = buckets[dist]
        # best first (your order_and_rank_route_stops already computed _route_score)
        pois.sort(key=lambda x: x.get("_route_score", x.get("_final_score", 0.0)), reverse=True)
        picked = []
        used = set()
        for p in pois:
            aid = p.get("attraction_id")
            if not aid or aid in used:
                continue
            picked.append(p)
            used.add(aid)
            if len(picked) >= per_district:
                break
        if picked:
            out.append({"district": dist, "attractions": picked})
    return out

def _build_one_plan(payload: Dict[str, Any], cfg: PlannerConfig, mode: PlanMode) -> Dict[str, Any]:
    payload = deepcopy(payload)
    payload["_plan_label"] = mode
    origin = str(payload.get("origin_city") or "").strip() or None
    dest = str(payload.get("city") or payload.get("destination") or "").strip() or "Colombo"
    payload["destination"] = dest
    payload["city"] = dest  # keep destination city stored
    if mode == "city":
        payload["travel_mode"] = {"type": "city", "include_stops": False}
        payload["on_the_way"] = False
        payload["route_direction"] = None
    elif mode == "corridor_outbound":
        payload["travel_mode"] = {"type": "corridor", "include_stops": True, "origin_city": origin}
        payload["on_the_way"] = True
        payload["route_direction"] = "outbound"
        # corridor leg is origin -> destination (normal)
    elif mode == "corridor_return":
        payload["travel_mode"] = {"type": "corridor", "include_stops": True, "origin_city": dest}
        payload["on_the_way"] = True
        payload["route_direction"] = "return"
        # swap for return leg
        payload["origin_city"] = dest              # ✅ IMPORTANT (origin is destination city)
        payload["city"] = origin or dest
        payload["destination"] = origin or dest
    return build_itinerary_from_payload(payload, cfg=cfg)

# ============================================================
# PATCH: Add this function BEFORE build_two_plans_from_payload
# in your itinerary_planner.py
# ============================================================

def _build_structured_itinerary(
    destination_plan: Dict[str, Any],
    hotels: List[Dict[str, Any]],
    shop_dine: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Merges attractions + hotel options + restaurants into a clean
    day-by-day structure that is easy for the frontend to render.

    - attractions : morning / afternoon slots with weather + crowd data
    - restaurants : evenly distributed across days (cafe, restaurant, fast_food, bakery only)
    - hotel_options: top-3 hotels shown on every day (user is staying there)
    """
    raw_days = destination_plan.get("itinerary") or []
    days = len(raw_days)
    if days == 0:
        return []

    # ------------------------------------------------------------------
    # 1. Filter to real dining places only
    # ------------------------------------------------------------------
    RESTAURANT_CATS = {"restaurant", "cafe", "fast_food", "bakery"}
    restaurants = [
        p for p in (shop_dine or [])
        if (p.get("category") or "").strip().lower() in RESTAURANT_CATS
    ]

    # ------------------------------------------------------------------
    # 2. Distribute restaurants evenly across days
    # ------------------------------------------------------------------
    def _chunk(lst: list, n: int):
        if n <= 0:
            return
        k, r = divmod(len(lst), n)
        i = 0
        for d in range(n):
            size = k + (1 if d < r else 0)
            yield lst[i: i + size]
            i += size

    restaurant_chunks = (
        list(_chunk(restaurants, days)) if restaurants else [[] for _ in range(days)]
    )

    # ------------------------------------------------------------------
    # 3. Top-3 hotel options (same for every day — user stays there)
    # ------------------------------------------------------------------
    top_hotels = (hotels or [])[:3]

    # ------------------------------------------------------------------
    # 4. Build day-by-day structure
    # ------------------------------------------------------------------
    structured = []
    for i, day in enumerate(raw_days):
        attractions = []
        for item in (day.get("items") or []):
            enrichment  = item.get("enrichment") or {}
            weather_raw = enrichment.get("weather") or {}
            weather_pt  = weather_raw.get("weather_point") or {}
            sustain     = enrichment.get("sustainability") or {}
            dynamic     = item.get("dynamic") or {}
            raw         = item.get("raw") or {}

            attractions.append({
                "slot":               item.get("slot"),
                "title":              item.get("title"),
                "attraction_id":      item.get("attraction_id"),
                "category":           raw.get("category"),
                "description":        raw.get("description"),
                "rating":             raw.get("rating"),
                "city":               item.get("city"),
                "district":           item.get("district"),
                "weather": {
                    "condition":  weather_pt.get("condition"),
                    "temp_c":     weather_pt.get("temp_c"),
                    "min_c":      weather_pt.get("min_c"),
                    "max_c":      weather_pt.get("max_c"),
                    "rain_risk":  weather_raw.get("rain_risk"),
                    "mean_mm":    weather_pt.get("mean_mm"),
                },
                "crowd_risk":         dynamic.get("crowd_risk_0_1"),
                "sustainability_score": sustain.get("score_0_1"),
                "sustainability_label": sustain.get("label"),
            })

        day_restaurants = []
        for r in restaurant_chunks[i]:
            day_restaurants.append({
                "title":       r.get("title"),
                "category":    r.get("category"),
                "rating":      r.get("rating"),
                "city":        r.get("city"),
                "district":    r.get("district"),
                "distance_km": r.get("distance_km"),
            })

        hotel_options = []
        for h in top_hotels:
            # price_range may come as "6210.0-7590.0" string or dict
            price = h.get("price_range") or h.get("price_range_lkr")
            hotel_options.append({
                "name":           h.get("name") or h.get("title"),
                "stars":          h.get("stars"),
                "price_range_lkr": price,
                "amenities":      h.get("amenities") or [],
                "city":           h.get("city"),
                "kg_id":          h.get("kg_id"),
            })

        structured.append({
            "date":         day.get("date"),
            "day_number":   i + 1,
            "city":         day.get("city"),
            "district":     day.get("district"),
            "attractions":  attractions,
            "restaurants":  day_restaurants,
            "hotel_options": hotel_options,
        })

    return structured



def build_two_plans_from_payload(payload: Dict[str, Any], cfg: PlannerConfig) -> Dict[str, Any]:
    """
    Returns plans in a single response.
    If 'origin_city' is None or empty, it ONLY generates the destination_plan.

    Top-level response now includes a clean `itinerary` array with
    attractions + restaurants + hotel_options merged per day.
    """
    origin = str(payload.get("origin_city") or "").strip()
    dest   = str(payload.get("city") or payload.get("destination") or "").strip()

    # =========================================================
    # PRECOMPUTE GRAPHHOPPER & KG CORRIDOR ONCE
    # =========================================================
    if origin and dest and origin.lower() != dest.lower():
        cities_path  = _cities_json_path()
        origin_coords = resolve_city_coords(origin, cities_json_path=cities_path)
        dest_coords   = resolve_city_coords(dest,   cities_json_path=cities_path)

        if origin_coords and dest_coords:
            route = fetch_route_sampled_points(
                origin=origin_coords,
                dest=dest_coords,
                profile="car",
                downsample_step_km=10.0,
            )
            graphhopper_dbg = {
                "distance_m":          route.distance_m,
                "time_ms":             route.time_ms,
                "route_points_count":  route.route_points_count,
                "sampled_points_count": route.sampled_points_count,
                "downsample_step_km":  10.0,
            }
            print("\n--- GRAPHHOPPER PREFLIGHT (PRECOMPUTED) ---")
            print(f"origin: {origin} {origin_coords}")
            print(f"dest  : {dest} {dest_coords}")
            print(f"dbg   : {graphhopper_dbg}")

            corridor_candidates, kg_corridor_dbg = fetch_corridor_attractions_from_kg(
                origin_city=origin,
                destination_city=dest,
                sampled_points=route.sampled_points,
                country=payload.get("country", "Sri Lanka"),
                corridor_km=15.0,
                limit=int(payload.get("max_candidates") or cfg.max_candidates),
                payload=payload,
            )

            payload["_precomputed_route"] = {
                "origin_coords":      origin_coords,
                "dest_coords":        dest_coords,
                "sampled_points":     route.sampled_points,
                "distance_m":         route.distance_m,
                "time_ms":            route.time_ms,
                "graphhopper_dbg":    graphhopper_dbg,
                "corridor_candidates": corridor_candidates,
                "kg_corridor_dbg":    kg_corridor_dbg,
            }

    # =========================================================
    # 1. Always build the destination (city) plan
    # =========================================================
    destination_plan = _build_one_plan(payload, cfg, mode="city")

    plans: Dict[str, Any] = {
        "destination_plan": destination_plan,
    }

    # =========================================================
    # 2. Build route plans only when origin differs from dest
    # =========================================================
    if origin and origin.lower() != dest.lower():
        plans["route_plan"]        = _build_one_plan(payload, cfg, mode="corridor_outbound")
        plans["route_return_plan"] = _build_one_plan(payload, cfg, mode="corridor_return")

    # =========================================================
    # 3. Collect hotels from destination plan
    # =========================================================
    hotels = destination_plan.get("hotels", {}).get("items") or []

    # =========================================================
    # 4. Collect shop/dine from whichever plan has items
    #    Priority: corridor outbound -> return -> destination
    # =========================================================
    shop_dine_items: List[Dict[str, Any]] = []
    for plan_key in ("route_plan", "route_return_plan", "destination_plan"):
        plan  = plans.get(plan_key) or {}
        items = plan.get("shopping_dining_on_route", {}).get("items") or []
        if items:
            shop_dine_items = items
            break

    # =========================================================
    # 5. Build the clean structured itinerary
    # =========================================================
    structured_itinerary = _build_structured_itinerary(
        destination_plan=destination_plan,
        hotels=hotels,
        shop_dine=shop_dine_items,
    )

    # =========================================================
    # 6. Return full response
    # =========================================================
    return {
        "status": "ok",
        "meta": {
            "destination":  payload.get("city") or payload.get("destination"),
            "origin_city":  payload.get("origin_city"),
            "days":         payload.get("days"),
            "start_date":   payload.get("start_date"),
        },

        # ✅ Clean day-by-day itinerary (attractions + restaurants + hotels)
        "itinerary": structured_itinerary,

        # Raw plans kept for debugging / route display on map
        "plans": plans,

        # Top-level raw hotel + shop/dine for any consumer that wants raw data
        "hotels": destination_plan.get("hotels") or {},
        "shopping_dining_on_route": {
            "items": shop_dine_items,
        },
    }
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
KG_BASE_URL = os.getenv("KG_BASE_URL", "http://localhost:8000").rstrip("/")
KG_SUB_ATTRACTIONS_PATH = "/sub-attractions/orchestrator/call/sub-attractions"
KG_RESOLVE_OD_PATH = "/geo/orchestrator/call/resolve-od"
def _parse_coords_from_kg(x: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    c = x.get("coordinates")
    if isinstance(c, str) and "," in c:
        a, b = c.split(",", 1)
        try:
            return float(a.strip()), float(b.strip())
        except Exception:
            return None, None
    # also support lat/lng fields if KG returns them later
    lat = x.get("lat") or x.get("latitude")
    lng = x.get("lng") or x.get("longitude")
    try:
        return (float(lat), float(lng)) if lat is not None and lng is not None else (None, None)
    except Exception:
        return None, None
def recommend_city_pois_simple(payload: Dict[str, Any], cfg: PlannerConfig = PlannerConfig()) -> Dict[str, Any]:
    """
    City-only:
    1. Fetch attractions from KG
    2. Rerank using enrich_and_rerank_candidates
    3. Return ranked list
    """
    city = str(payload.get("city") or "").strip()
    if not city:
        raise ValueError("city is required")
    country = str(payload.get("country") or "Sri Lanka").strip()
    # --------------------------
    # 1️⃣ Fetch from KG
    # --------------------------
    candidates, dbg = fetch_city_attractions_from_kg(
        city=city,
        country=country,
        limit=int(payload.get("max_candidates") or cfg.max_candidates),
        timeout=40.0,
    )
    # Optional: ensure strict city match
    candidates = [c for c in candidates if _safe_city_match(c, city)]
    if not candidates:
        return {
            "status": "ok",
            "city": city,
            "country": country,
            "items": [],
            "warnings": [f"No attractions found for city='{city}'."],
        }
    # Add eco hint so reranker works correctly
    for c in candidates:
        c["_eco_hint"] = _eco_score_hint(c)
        c["_score"] = float(c.get("_score", 0.0))
    # --------------------------
    # 2️⃣ Preference rerank
    # --------------------------
    # 1️⃣ Extract priorities from payload
    priorities = extract_priorities(payload)
    # 2️⃣ Compute rank score using preferences ONLY (no date logic)
    for c in candidates:
        c["_eco_hint"] = _eco_score_hint(c)
        c["_final_score"] = compute_rank_score(
            rec=c,
            priorities=priorities,
            eco_preference=float(payload.get("eco_preference") or 0.5),
        )
    # 3️⃣ Sort by final score
    reranked = sorted(
        candidates,
        key=lambda x: x.get("_final_score", 0.0),
        reverse=True
    )
    # Apply limit
    limit = int(payload.get("limit") or 20)
    reranked = reranked[:limit]
    # --------------------------
    # 3️⃣ Clean response
    # --------------------------
    items = []
    for c in reranked:
        items.append({
            "attraction_id": c.get("attraction_id"),
            "title": c.get("title"),
            "category": c.get("category"),
            "description": c.get("description"),
            "city": c.get("city"),
            "district": c.get("district"),
            "province": c.get("province"),
            "rating": c.get("rating"),
            "lat": c.get("lat"),
            "lng": c.get("lng"),
            "rank_score_base": float(c.get("_score", 0.0)),
            "rank_score_final": float(c.get("_final_score", c.get("_score", 0.0))),
            "recommended_because": c.get("_reasons", []),
            "matched_preferences": {
                "tags": payload.get("tags", []),
                "avoid_crowds": payload.get("avoid_crowds"),
                "eco_preference": payload.get("eco_preference"),
            },
            "score_breakdown": c.get("_score_breakdown", {}),
            "dynamic": c.get("_dynamic", {}),
        })
    return {
        "status": "ok",
        "mode": "city_recommendation",
        "city": city,
        "country": country,
        "items": items,
    }
def _kg_item_to_candidate(x: Dict[str, Any]) -> Dict[str, Any]:
    title = (x.get("title") or x.get("name") or "").strip()
    if not title:
        return {}
    district = (x.get("district") or x.get("city") or "").strip()
    attraction_id = x.get("attraction_id") or normalize_to_attraction_id({
        "title": title,
        "district": district,
        "city": x.get("city"),
        "province": x.get("province"),
        "name": x.get("name"),
    })
    # ✅ KG corridor fields
    lat = x.get("lat") or x.get("latitude")
    lng = x.get("lng") or x.get("lon") or x.get("longitude")
    try:
        lat = float(lat) if lat is not None else None
        lng = float(lng) if lng is not None else None
    except Exception:
        lat, lng = None, None
    return {
        "attraction_id": attraction_id,
        "title": title,
        "category": x.get("category"),
        "description": x.get("editorial_summary") or x.get("description"),
        "city": x.get("city"),
        "district": x.get("district"),
        "province": x.get("province"),
        "location": x.get("formatted_address") or x.get("parent_location"),
        "rating": x.get("rating"),
        "lat": lat,
        "lng": lng,
        "source": x.get("source", "kg_service"),
        # keep corridor metadata for visualization
        "_route_point": x.get("_route_point"),
        "_route_point_index": x.get("_route_point_index"),
        "_distance_km": x.get("distance_km"),
        "_kg_raw": x,
    }
def fetch_city_attractions_from_kg(
    city: str,
    country: str = "Sri Lanka",
    limit: int = 60,
    timeout: float = 40.0,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Calls KG endpoint and returns (candidates, debug)
    """
    url = f"{KG_BASE_URL}{KG_SUB_ATTRACTIONS_PATH}"
    payload = {
        "city": city,
        "country": country,
        "limit": limit,
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    items = data.get("items") or []
    candidates = [_kg_item_to_candidate(x) for x in items if isinstance(x, dict)]
    debug = {
        "kg_url": url,
        "kg_payload": payload,
        "kg_returned": len(items),
        "candidates_returned": len(candidates),
    }
    return candidates, debug
KG_CORRIDOR_ATTRACTIONS_PATH = "/Recommender/call/attractions-on-route"
def fetch_corridor_attractions_from_kg(
    origin_city: str,
    destination_city: str,
    sampled_points: List[Tuple[float, float]],  # [(lat, lon), ...]
    *,
    country: str = "Sri Lanka",
    corridor_km: float = 15.0,
    limit: int = 80,
    timeout: float = 40.0,
    payload: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Send downsampled route points to KG and get attractions along the corridor.
    """
    url = f"{KG_BASE_URL}{KG_CORRIDOR_ATTRACTIONS_PATH}"
    body = {
        "country": country,
        "origin_city": origin_city,
        "destination_city": destination_city,
        "corridor_km": corridor_km,
        "limit": limit,
        # IMPORTANT: keep consistent format. Use [lat, lon] since your points are (lat, lon)
        "sampled_route_points": [[lat, lon] for (lat, lon) in sampled_points],
    }
    if payload:
        body["semantic"] = {
            "enabled": True,
            "query": build_semantic_query(payload),
            "fields": ["groups", "editorial_summary", "category", "name"],
            "weight": 0.35,
        }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=body)
        r.raise_for_status()
        data = r.json()
        items = data.get("items") or []
        flat_pois: List[Dict[str, Any]] = []
        # ✅ NEW: take fair share from each route point so we cover the whole corridor
        n_points = max(1, len(items))
        per_point_limit = max(2, int(limit / n_points) + 1)   # tune: 2..4 works well
        # Example: limit=80, points=40 => per_point_limit ~ 3
        for grp in items:
            if not isinstance(grp, dict):
                continue
            rp = grp.get("route_point")              # [lat, lon]
            rpi = grp.get("route_point_index")       # int
            subs = grp.get("sub_attractions") or []  # list[dict]
            taken = 0
            for s in subs:
                if not isinstance(s, dict):
                    continue
                s["_route_point"] = rp
                s["_route_point_index"] = rpi
                flat_pois.append(s)
                taken += 1
                if taken >= per_point_limit:
                    break
        # ✅ Now enforce overall limit AFTER balancing
        if len(flat_pois) > limit:
            flat_pois = flat_pois[:limit]
            # ✅ convert flat POIs into normalized candidates
        candidates = []
        for x in flat_pois:
            c = _kg_item_to_candidate(x)
            if c:
                candidates.append(c)
    debug = {
        "kg_url": url,
        "kg_request": body,
        "kg_returned": len(items),
        "candidates_returned": len(candidates),
    }
    return candidates, debug
def fetch_origin_dest_coords_from_kg(
    origin_city: str,
    destination_city: str,
    country: str = "Sri Lanka",
    timeout: float = 40.0,
) -> Dict[str, Any]:
    """
    Sends origin_city + destination_city to KG to resolve coords.
    KG endpoint may not exist yet -> will raise httpx error (that's OK for now).
    """
    url = f"{KG_BASE_URL}{KG_RESOLVE_OD_PATH}"
    body = {
        "origin_city": origin_city,
        "destination_city": destination_city,
        "country": country,
    }
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=body)
        r.raise_for_status()
        return r.json()
@dataclass
class Priority:
    key: str                # canonical key e.g. "eco-friendly"
    weight: float           # higher means more important
    source: str             # "raw_text" | "structured"
    matched_phrase: str     # what matched in text
@dataclass
class CandidatesResult:
    candidates: List[Dict[str, Any]]
    debug: Dict[str, Any]
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
from collections import defaultdict
def group_by_district(candidates):
    buckets = defaultdict(list)
    for p in candidates:
        d = p.get("district") or p.get("city") or "unknown"
        buckets[d].append(p)
    for d in buckets:
        # ✅ NEW: Sort by Pareto flag first (True > False), then final score
        buckets[d].sort(key=lambda x: (x.get("_is_pareto", False), x.get("_final_score", x.get("_score", 0.0))), reverse=True)
    return buckets
def district_centroid(pois):
    lats = []
    lngs = []
    for p in pois:
        # Check both "lat"/"lng" and "latitude"/"longitude"
        lat = p.get("lat") if p.get("lat") is not None else p.get("latitude")
        lng = p.get("lng") if p.get("lng") is not None else p.get("longitude")
        if lat is not None and lng is not None:
            try:
                lats.append(float(lat))
                lngs.append(float(lng))
            except (ValueError, TypeError):
                continue
    if not lats or not lngs:
        return None
    return (sum(lats) / len(lats), sum(lngs) / len(lngs))
def order_districts(buckets, start_coords, is_return=False):
    if not start_coords:
        return list(buckets.keys())
    sx, sy = start_coords
    centroids = []
    for d, pois in buckets.items():
        c = district_centroid(pois)
        if c is None: continue
        centroids.append((d, c))
    # Calculate squared distance from start_coords
    # If is_return is True, sx/sy will be Kandy coords, and we move towards Colombo
    centroids.sort(key=lambda x: (x[1][0] - sx) ** 2 + (x[1][1] - sy) ** 2)
    return [d for d, _ in centroids]
def _norm_city_key(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()
def build_itinerary(ranked_candidates, days, per_day=2, anchor=None):
    buckets = group_by_district(ranked_candidates)
    ordered_districts = order_districts(buckets, anchor)
    itinerary = []
    used = set()
    for day in range(days):
        if not ordered_districts:
            break
        # Look at the current district (don't pop it immediately!)
        district = ordered_districts[0]
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
        # --- NEW LOGIC: Decide whether to move to the next district ---
        remaining_unused = [p for p in pois if p.get("attraction_id") not in used]
        remaining_days = days - (day + 1)
        other_districts_count = len(ordered_districts) - 1
        # Move to the next district ONLY IF:
        # 1. We are completely out of unused attractions here.
        # 2. OR we need all the remaining days to visit the rest of the districts on our route.
        if not remaining_unused or other_districts_count >= remaining_days:
            ordered_districts.pop(0)
    return itinerary
def order_and_rank_route_stops(route_candidates, priorities, eco_pref):
    buckets = defaultdict(list)
    for c in route_candidates:
        rpi = c.get("_route_point_index")
        if rpi is None:
            rpi = 10**9
        c["_eco_hint"] = _eco_score_hint(c)
        # existing: your rule/preference score
        c["_pref_score"] = compute_rank_score(c, priorities, eco_pref)
        # ✅ Step 2: semantic + dynamic blend (assumes attach_semantic_scores already ran)
        sem   = float(c.get("_semantic_sim", 0.0))          # 0..1 (usually)
        final = float(c.get("_final_score", 0.0))           # from enrich_and_rerank_candidates
        pref  = float(c.get("_pref_score", 0.0))            # from compute_rank_score
        # pick weights (tune later)
        c["_route_score"] = (0.55 * final) + (0.30 * sem) + (0.15 * pref)
        buckets[rpi].append(c)
    ordered = []
    for rpi in sorted(buckets.keys()):
        group = buckets[rpi]
        group.sort(key=lambda x: x.get("_route_score", x.get("_final_score", 0.0)), reverse=True)
        ordered.extend(group)
    return ordered
def _has_attraction_focused_style(payload: Dict[str, Any]) -> bool:
    """
    If the user travel_style suggests sightseeing (eco/family/etc),
    we should omit restaurants/shops from corridor POIs.
    """
    styles = payload.get("travel_style") or []
    styles_l = {str(s).strip().lower() for s in styles if s}
    # your example: ['eco-friendly', 'family']
    attraction_styles = {
        "eco-friendly", "eco friendly", "eco",
        "family", "family-friendly", "family friendly",
        "cultural", "heritage",
        "adventure", "relaxation", "romantic",
        "nature", "wildlife"
    }
    # If user explicitly asked for food, don't filter restaurants
    food_styles = {"food", "cuisine", "dining", "restaurants", "street food"}
    if styles_l & food_styles:
        return False
    return bool(styles_l & attraction_styles)
def _is_non_attraction_poi(c: Dict[str, Any]) -> bool:
    """
    Conservative filter for non-attraction POIs (restaurants, shopping, hotels, etc.)
    Uses the fields you actually have from KG: name/category/groups/editorial_summary.
    """
    name = str(c.get("title") or c.get("name") or "").lower()
    category = str(c.get("category") or "").lower()
    summary = str(c.get("description") or c.get("editorial_summary") or "").lower()
    groups = " ".join([str(g).lower() for g in (c.get("groups") or [])])
    blob = " ".join([name, category, summary, groups])
    # fast explicit brand kills
    brand_kills = [
        "kfc", "mcdonald", "pizza hut", "domino", "burger king",
        "keells", "cargills", "food city"
    ]
    if any(b in blob for b in brand_kills):
        return True
    # category/groups kills from your raw response
    category_kills = {
        "fast_food", "restaurant", "cafe", "bakery", "bar",
        "supermarket", "grocery", "store", "shopping_mall", "mall", "shop",
        "lodging", "hotel", "resort"
    }
    if category in category_kills:
        return True
    # group-based kills (your response has "Food & Markets", "Shopping & City")
    group_kills = {"food & markets", "shopping & city", "shopping", "food"}
    if any(gk in groups for gk in group_kills):
        return True
    # keyword kills (catch other variations)
    kw_kills = [
        "restaurant", "cafe", "coffee", "bakery",
        "supermarket", "grocery", "shopping", "mall", "store",
        "hotel", "resort"
    ]
    if any(k in blob for k in kw_kills):
        return True
    return False

KG_HOTEL_SEARCH_PATH = "/hotels/orchestrator/call/hotels/search"


def fetch_hotels_for_destination(
    payload: Dict[str, Any],
    *,
    timeout: float = 40.0,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetch hotels from the KG hotel search endpoint for the destination city.

    Only sends the minimal required fields:
      - payload["destination"] | payload["city"]  ->  request["city"]
      - payload["raw_text"]                        ->  request["raw_text"]
      - payload["user_id"]                         ->  request["user_id"]
      - payload["session_id"]                      ->  request["session_id"]
      - intent is always "info_accommodation"
    """
    url = f"{KG_BASE_URL}{KG_HOTEL_SEARCH_PATH}"

    # ✅ KEY MAPPING: "destination" from orchestrator payload -> "city" in hotel search
    destination = str(
        payload.get("destination") or payload.get("city") or ""
    ).strip()

    body: Dict[str, Any] = {
        "intent": "info_accommodation",
        "raw_text": str(payload.get("raw_text") or f"hotels in {destination}"),
        "user_id": str(payload.get("user_id") or "system"),
        "session_id": str(payload.get("session_id") or "itinerary-planner"),
        "city": destination,
    }

    body["limit"] = int(payload.get("hotel_limit") or 10)

    debug = {
        "hotel_search_url": url,
        "hotel_search_body": body,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=body)
            r.raise_for_status()
            data = r.json()

        items = data.get("items") or []
        debug["hotel_count"] = len(items)
        debug["ok"] = data.get("ok", True)
        return items, debug

    except Exception as exc:
        debug["error"] = str(exc)
        debug["hotel_count"] = 0
        print(f"[HOTEL FETCH] Error fetching hotels for '{destination}': {exc}")
        return [], debug


KG_SHOP_DINE_PATH = "/Recommender/call/shopping-and-dining-on-route"

def fetch_shop_dine_on_route_from_kg(
    origin_city: str,
    destination_city: str,
    sampled_points: List[Tuple[float, float]],
    *,
    country: str = "Sri Lanka",
    corridor_km: float = 10.0,
    limit: int = 120,
    timeout: float = 40.0,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    url = f"{KG_BASE_URL}{KG_SHOP_DINE_PATH}"
    body = {
        "country": country,
        "origin_city": origin_city,
        "destination_city": destination_city,
        "corridor_km": corridor_km,
        "limit": limit,
        "sampled_route_points": [[lat, lon] for (lat, lon) in sampled_points],
    }

    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=body)
        r.raise_for_status()
        data = r.json()

    items = data.get("items") or []
    flat: List[Dict[str, Any]] = []

    for grp in items:
        if not isinstance(grp, dict):
            continue
        rp  = grp.get("route_point")        # [lat, lon]
        rpi = grp.get("route_point_index")  # int
        subs = grp.get("sub_attractions") or []
        for s in subs:
            if not isinstance(s, dict):
                continue
            s["_route_point"] = rp
            s["_route_point_index"] = rpi
            flat.append(s)

    # normalize to your candidate structure
    candidates: List[Dict[str, Any]] = []
    for x in flat[:limit]:
        c = _kg_shop_dine_item_to_candidate(x)
        if c:
            candidates.append(c)

    debug = {"kg_url": url, "kg_request": body, "kg_returned": len(items), "candidates_returned": len(candidates)}
    return candidates, debug


def _kg_shop_dine_item_to_candidate(x: Dict[str, Any]) -> Dict[str, Any]:
    name = (x.get("name") or x.get("title") or "").strip()
    if not name:
        return {}

    # categories you showed: fast_food, supermarket, etc.
    category = (x.get("category") or "").strip().lower()

    lat = x.get("latitude") or x.get("lat")
    lng = x.get("longitude") or x.get("lng") or x.get("lon")

    try:
        lat = float(lat) if lat is not None else None
        lng = float(lng) if lng is not None else None
    except Exception:
        lat, lng = None, None

    # unique-ish id
    poi_id = normalize_to_attraction_id({
        "title": name,
        "district": x.get("district"),
        "city": x.get("city"),
        "province": x.get("province"),
    })

    return {
        "poi_id": poi_id,
        "title": name,
        "category": category,
        "groups": x.get("groups") or [],
        "description": x.get("editorial_summary") or x.get("description"),
        "city": x.get("city"),
        "district": x.get("district"),
        "province": x.get("province"),
        "location": x.get("formatted_address") or x.get("parent_location"),
        "rating": x.get("rating"),
        "lat": lat,
        "lng": lng,
        "distance_km": x.get("distance_km"),
        "_route_point": x.get("_route_point"),
        "_route_point_index": x.get("_route_point_index"),
        "_kg_raw": x,
    }

def _shop_category_rank(cat: str) -> int:
    c = (cat or "").strip().lower()

    # normalize common variants
    if c in ("restuarent",):   # typo safety
        c = "restaurant"

    # lower number = earlier
    order = {
        "fast_food": 0,
        "restaurant": 1,
        "cafe": 2,
        "bakery": 3,
        # everything else goes here
        "supermarket": 99,     # ✅ always last
    }
    return order.get(c, 50)
def order_shop_dine_along_route(
    pois: List[Dict[str, Any]],
    sampled_points: List[Tuple[float, float]],
    *,
    route_direction: str = "outbound",   # "outbound" | "return"
) -> List[Dict[str, Any]]:
    # attach nearest sampled point index + nearest route point coords
    attach_nearest_route_point(pois, sampled_points)

    # sort: along route first, then by category rank, then by closeness to route, then rating
    pois.sort(
        key=lambda x: (
            x.get("_nearest_point_index") if x.get("_nearest_point_index") is not None else 10**9,
            _shop_category_rank(x.get("category")),
            x.get("_nearest_point_km") if x.get("_nearest_point_km") is not None else 10**9,
            -(float(x.get("rating") or 0.0)),
        )
    )

    if (route_direction or "").lower() == "return":
        pois.reverse()

    # ✅ include the GraphHopper point lat/lon explicitly in each item
    for p in pois:
        np = p.get("_nearest_point")
        if isinstance(np, tuple) and len(np) == 2:
            p["route_lat"] = float(np[0])
            p["route_lon"] = float(np[1])
        else:
            p["route_lat"] = None
            p["route_lon"] = None

    return pois

def build_itinerary_days_from_pool(
    *,
    pool: List[Dict[str, Any]],
    city: str,
    country: str,
    start_dt: date,
    days: int,
    per_day: int,
    eco_pref: float,
    explicit_city_for_enrich: str,
) -> List[Dict[str, Any]]:
    simple_itinerary = build_itinerary(
        ranked_candidates=pool,
        days=days,
        per_day=per_day,
        anchor=None,
    )

    itinerary_days: List[Dict[str, Any]] = []
    slots = ["morning", "afternoon"]

    for i, day_pack in enumerate(simple_itinerary):
        day_number = int(day_pack.get("day") or (i + 1))
        day_date = start_dt + timedelta(days=day_number - 1)
        day_str = day_date.isoformat()

        day_items: List[Dict[str, Any]] = []
        for idx, a in enumerate(day_pack["attractions"]):
            item_city = a.get("city") or a.get("district") or city
            aid = a["attraction_id"]

            enrich = a.get("_enrichment") or enrich_attraction(
                attraction_id=aid,
                date_str=day_str,
                eco_preference=eco_pref,
                country=country,
                explicit_city=explicit_city_for_enrich,  # ✅ keep same behavior
            )

            day_items.append({
                "slot": slots[idx] if idx < len(slots) else f"slot_{idx+1}",
                "kind": "attraction",
                "attraction_id": aid,
                "title": a.get("title") or a.get("name"),
                "district": a.get("district"),
                "city": item_city,
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

    return itinerary_days
def run_city_pipeline(city_name: str, payload: Dict[str, Any], cfg: PlannerConfig) -> Dict[str, Any]:
    """
    Runs: KG fetch -> TOP15 print -> rerank -> NSGA -> returns pareto_pool + debug packs
    Same as destination logic but parameterized by city_name.
    """
    country = str(payload.get("country") or "Sri Lanka").strip() or "Sri Lanka"
    eco_pref = float(payload.get("eco_preference") or 0.5)

    # 1) KG fetch for this city
    candidates, kg_dbg = fetch_city_attractions_from_kg(
        city=city_name,
        country=country,
        limit=int(payload.get("max_candidates", cfg.max_candidates)),
        timeout=40.0,
    )

    # prep candidate features (same as your destination setup)
    for c in candidates:
        c["_eco_hint"] = _eco_score_hint(c)
        c["_score"] = float(c.get("_score", 0.0))
        c["_features"] = {"eco_hint": float(c.get("_eco_hint", 0.5))}

    # TOP-15 debug (same print format)
    print(f"\n================ WAYPOINT CITY: {city_name} ================")
    print("[TOP-15 KG IDS]")
    for a in candidates[:15]:
        print(a.get("attraction_id"), "|", a.get("district"), "|", a.get("title"))

    print("\n--- Top KG Ranked Attractions (base _score) ---")
    for a in candidates[:10]:
        feat = a.get("_features", {}) or {}
        print(
            f"{a.get('title','?'):<25} | base={a.get('_score', 0.0):.3f} | "
            f"eco={feat.get('eco_hint', 0.0):.2f}"
        )

    # 2) Rerank (same config)
    reranked = enrich_and_rerank_candidates(
        candidates=candidates,
        payload=payload,
        cfg=EnrichConfig(
            w_sustainability=1.2,
            w_crowd_avoid=0.8,
            w_rain_avoid=0.6,
        ),
        day_offset=0,
    )

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

    # 3) Destination filtering for THIS city (reuse your existing matcher)
    city_reranked = [c for c in reranked if _is_destination_candidate(c, city_name)]

    # 4) NSGA (same)
    obj_vectors = []
    for i, cand in enumerate(city_reranked):
        objectives, explain = build_objectives(cand, payload)
        cand["_nsga_objectives"] = objectives
        cand["_nsga_explain"] = explain
        obj_vectors.append((objectives, i))

    front_indices = pareto_front(obj_vectors)
    pareto_pool = [city_reranked[i] for i in front_indices]

    print("\n--- NSGA-II Pareto Front ---")
    for c in pareto_pool[:10]:
        e = c["_nsga_explain"]
        print(
            f"{c.get('title','?'):<25} | "
            f"match={e['match_0_1']:.2f} sus={e['sustainability_0_1']:.2f} "
            f"crowd={e['crowd_risk_0_1']:.2f} rain={e['rain_risk_0_1']:.2f}"
        )

    return {
        "city": city_name,
        "kg_dbg": kg_dbg,
        "pareto_pool": pareto_pool,
    }
def build_wayout_stop_plans_from_route_candidates(
    *,
    route_candidates: List[Dict[str, Any]],
    waypoints: List[str],
    stop_days_map: Dict[str, int],
    start_dt: date,
    country: str,
    per_day: int,
    eco_pref: float,
) -> List[Dict[str, Any]]:
    """
    Builds separate destination-like plans for each waypoint stop
    using the *already filtered/scored/sorted* corridor route candidates.

    - Filters route_candidates by waypoint area (district/city match)
    - Takes top (days * per_day) items for that stop
    - Builds itinerary_days like destination plan
    - Advances date cursor after each stop
    """
    out: List[Dict[str, Any]] = []
    wp_cursor_dt = start_dt

    # safety: normalize waypoints
    waypoints = [str(w or "").strip() for w in (waypoints or []) if str(w or "").strip()]

    for wp_city in waypoints:
        wp_days = int(stop_days_map.get(wp_city) or 1)

        # 1) Filter: only POIs belonging to this waypoint area
        # 2) Cap to what we can schedule
        cap = max(1, wp_days * per_day)
        wp_pool = [c for c in route_candidates if _is_destination_area(c, wp_city)]
        wp_pool.sort(key=lambda x: x.get("_route_score", x.get("_final_score", 0.0)), reverse=True)
        wp_pool = wp_pool[:cap]

        # 3) Build itinerary_days (destination-like)
        wp_itinerary_days = build_itinerary_days_from_pool(
            pool=wp_pool,
            city=wp_city,
            country=country,
            start_dt=wp_cursor_dt,
            days=wp_days,
            per_day=per_day,
            eco_pref=eco_pref,
            explicit_city_for_enrich=wp_city,  # ✅ IMPORTANT: enrich using waypoint city
        )

        out.append({
            "status": "ok",
            "plan_type": "wayout_stop",
            "waypoint_city": wp_city,
            "start_date": wp_cursor_dt.isoformat(),
            "days": wp_days,
            "itinerary": wp_itinerary_days,
            "debug": {
                "matched_candidates": len(wp_pool),
                "source": "corridor_candidates_final",
            },
        })

        # 4) Advance cursor
        wp_cursor_dt = wp_cursor_dt + timedelta(days=wp_days)

    return out

def build_itinerary_days_simple_chunk(
    *,
    pool: List[Dict[str, Any]],
    city: str,
    country: str,
    start_dt: date,
    days: int,
    per_day: int,
    eco_pref: float,
    explicit_city_for_enrich: str,
) -> List[Dict[str, Any]]:
    days = max(1, int(days or 1))
    per_day = max(1, int(per_day or 1))

    # ✅ DO NOT CAP — we want ALL items
    pool = pool or []

    itinerary_days: List[Dict[str, Any]] = []
    base_slots = ["morning", "afternoon"]

    idx = 0
    for d in range(days):
        day_date = start_dt + timedelta(days=d)
        day_str = day_date.isoformat()

        day_items: List[Dict[str, Any]] = []
        for j in range(per_day):
            if idx >= len(pool):
                break

            a = pool[idx]
            idx += 1

            aid = a.get("attraction_id")
            if not aid:
                continue

            slot = base_slots[j] if j < len(base_slots) else f"slot_{j+1}"
            item_city = a.get("city") or a.get("district") or city

            enrich = a.get("_enrichment") or enrich_attraction(
                attraction_id=aid,
                date_str=day_str,
                eco_preference=eco_pref,
                country=country,
                explicit_city=explicit_city_for_enrich,  # ✅ waypoint city
            )

            day_items.append({
                "slot": slot,
                "kind": "attraction",
                "attraction_id": aid,
                "title": a.get("title") or a.get("name"),
                "district": a.get("district"),
                "city": item_city,
                "rank_score_base": float(a.get("_score", 0.0)),
                "rank_score_final": float(a.get("_final_score", a.get("_score", 0.0))),
                "dynamic": a.get("_dynamic", {}),
                "enrichment": enrich,
                "raw": {k: v for k, v in a.items() if not str(k).startswith("_")},
            })

        itinerary_days.append({
            "date": day_str,
            "city": city,
            "district": None,
            "items": day_items
        })

    return itinerary_days

def build_itinerary_from_payload(payload: Dict[str, Any], cfg: PlannerConfig = PlannerConfig()) -> Dict[str, Any]:
    city = str(payload.get("city") or payload.get("destination") or "").strip() or "Colombo"
    country = str(payload.get("country") or "Sri Lanka").strip() or "Sri Lanka"
    eco_pref = float(payload.get("eco_preference") or 0.5)
    # days used multiple times
    days = int(payload.get("days") or 3)
    start_str = str(payload.get("start_date") or "").strip()
    if not start_str:
        raise ValueError("payload.start_date required (YYYY-MM-DD)")
    y, m, d = [int(x) for x in start_str.split("-")]
    start_dt = date(y, m, d)
    warnings: List[str] = []
    waypoint_plans: List[Dict[str, Any]] = []  # ✅ ALWAYS exists (fixes corridor plan crash)
    # =========================
    # NEW: travel_mode decision
    # =========================
    tm = resolve_travel_mode(payload)
    plan_label = str(payload.get("_plan_label") or "")
    is_corridor_plan = plan_label in ("corridor_outbound", "corridor_return")
    cities_path = _cities_json_path()
    origin_city_pf = (tm.origin_city or payload.get("origin_city") or "").strip()
    dest_city_pf   = (tm.destination_city or payload.get("destination") or payload.get("city") or "").strip()
    waypoints = payload.get("waypoints") or []
    stop_days_map = payload.get("stop_durations_days") or {}
    print(
        f"\n[PLAN] {payload.get('_plan_label')}  tm={tm.type} include_stops={tm.include_stops} "
        f"origin={tm.origin_city} dest={tm.destination_city}"
        f"| payload.origin={payload.get('origin_city')} payload.dest={payload.get('destination') or payload.get('city')}"
    )
    # --------------------------
    # =========================
    # GRAPHHOPPER PREFLIGHT
    # =========================
    origin_coords = None
    dest_coords   = None
    sampled_points = []
    distance_m = None
    time_ms = None
    graphhopper_dbg = {"skipped": True, "reason": "missing coords or precomputed not triggered"}
    corridor_candidates = []
    route_candidates: List[Dict[str, Any]] = []
    kg_corridor_dbg = {"skipped": True, "reason": "not corridor mode"}
    route_direction = str(payload.get("route_direction") or "").strip().lower()
    precomputed = payload.get("_precomputed_route")
    if precomputed:
        # Swap coords if this is the return trip
        if route_direction == "return":
            origin_coords = precomputed["dest_coords"]
            dest_coords   = precomputed["origin_coords"]
        else:
            origin_coords = precomputed["origin_coords"]
            dest_coords   = precomputed["dest_coords"]
        if tm.type == "corridor" and tm.include_stops:
            sampled_points = precomputed["sampled_points"]
            distance_m = precomputed["distance_m"]
            time_ms = precomputed["time_ms"]
            graphhopper_dbg = precomputed["graphhopper_dbg"]
            # Deepcopy so changes in one plan don't bleed into the others
            import copy
            corridor_candidates = copy.deepcopy(precomputed["corridor_candidates"])
            kg_corridor_dbg = precomputed["kg_corridor_dbg"]
    payload["_graphhopper"] = graphhopper_dbg
    payload["_od_coords"] = {
        "origin_city": origin_city_pf,
        "destination_city": dest_city_pf,
        "origin_coords": origin_coords,
        "destination_coords": dest_coords,
    }
    # # ----------------------------
    route_start_coords = None
    # # ✅ priorities exist in this scope
    priorities: List[Priority] = extract_priorities(payload) or []
    route_direction = str(payload.get("route_direction") or "").strip().lower()
    # ==========================================================
    # NEW: switch KG query mode (corridor vs destination-only)
    # ==========================================================
    repo_root = _find_repo_root()
    kg_path = repo_root / "data" / "recommender_service" / "clean" / "kg" / "attractions_clean.json"
    # if tm.type == "corridor" and tm.include_stops and tm.origin_city and tm.origin_city != tm.destination_city:
    #     res = get_candidates_corridor(
    #         payload=payload,
    #         origin_city=tm.origin_city,
    #         dest_city=tm.destination_city,
    #         limit=int(payload.get("max_candidates", cfg.max_candidates)),
    #     )
    # ==========================================================
    # NEW: switch KG query mode (corridor vs destination-only)
    # ==========================================================
    kg_mode = "city"  # default
    if tm.type == "corridor" and tm.include_stops and tm.origin_city and tm.origin_city != tm.destination_city:
        dbg = kg_corridor_dbg
        kg_mode = "corridor_kg_points"
        origin_city = (payload.get("origin_city") or tm.origin_city or "").strip()
        dest_city   = (payload.get("destination") or payload.get("city") or "").strip()
        exclude_city = origin_city
        route_candidates = list(corridor_candidates)
        # ✅ filter ONCE (if attraction-focused)
        if _has_attraction_focused_style(payload):
            before = len(route_candidates)
            route_candidates = [c for c in route_candidates if not _is_non_attraction_poi(c)]
            after = len(route_candidates)
            print(f"[CORRIDOR FILTER] attraction-focused travel_style -> removed {before-after} non-attraction POIs (kept {after})")
        shop_dine, shop_dbg = fetch_shop_dine_on_route_from_kg(
            origin_city=origin_city,
            destination_city=dest_city,
            sampled_points=sampled_points,
            country=country,
            corridor_km=10.0,
            limit=120,
        )

        shop_dine = order_shop_dine_along_route(
            shop_dine,
            sampled_points,
            route_direction=route_direction,
        )

        payload["_shopping_dining_on_route"] = {
            "items": shop_dine,
            "debug": shop_dbg,
        }
        # ✅ MUST happen BEFORE scoring/sorting
        attach_nearest_route_point(route_candidates, sampled_points)
        # ✅ semantic after cleaning + snapping
        attach_semantic_scores(route_candidates, payload)
        # ✅ compute _route_score
        route_candidates = order_and_rank_route_stops(route_candidates, priorities, eco_pref)
        # ✅ enforce corridor direction ordering using nearest sampled point index
        # order by route position (origin -> destination)
        route_candidates.sort(
            key=lambda x: (
                x.get("_nearest_point_index") if x.get("_nearest_point_index") is not None else 10**9,
                x.get("_nearest_point_km") if x.get("_nearest_point_km") is not None else 10**9,
            )
        )
        # if return trip, just reverse the exact same ordered list
        if route_direction == "return":
            route_candidates.reverse()
        way_out_stop_plans = []
        waypoints = payload.get("waypoints") or []
        stop_days_map = payload.get("stop_durations_days") or {}
        per_day = int(payload.get("per_day_attractions") or cfg.per_day_attractions)

        # Only build if user provided stop durations / waypoints
        if waypoints and stop_days_map:
            way_out_stop_plans = build_wayout_stop_plans_from_route_candidates(
                route_candidates=route_candidates,
                waypoints=waypoints,
                stop_days_map=stop_days_map,
                start_dt=start_dt,          # uses same trip start; or change if you want after destination
                country=country,
                per_day=per_day,
                eco_pref=eco_pref,
            )
        # store into payload so it returns in response
        payload["_way_out_stop_plans"] = way_out_stop_plans
        res = CandidatesResult(candidates=route_candidates, debug=kg_corridor_dbg)
    else:
        # ✅ city mode: fetch from KG service
        city_for_query = tm.destination_city or city
        candidates, kg_dbg = fetch_city_attractions_from_kg(
            city=city_for_query,
            country=country,
            limit=int(payload.get("max_candidates", cfg.max_candidates)),
            timeout=20.0,
        )
        for c in candidates:
            c["_eco_hint"] = _eco_score_hint(c)
            c["_score"] = float(c.get("_score", 0.0))
            c["_features"] = {"eco_hint": float(c.get("_eco_hint", 0.5))}
        # ✅ Build "way-out stop" plans from final corridor candidates
        
        res = CandidatesResult(candidates=candidates, debug=kg_dbg)
        dbg = kg_dbg
        sampled_points = []
        kg_mode = "city"
        # ✅ debug dict (safe)
        dbg = getattr(res, "debug", None) or {}
        # keep dbg priorities in sync for your printing
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
        print("=======================================================\n")
        # -----------------------------------------------------
    # ✅ candidates
    kg_atts = getattr(res, "candidates", None) or []
    if not is_corridor_plan:
        print("[TOP-15 KG IDS]")
        for a in kg_atts[:15]:
            print(a.get("attraction_id"), "|", a.get("district"), "|", a.get("title"))
        print("\n--- Top KG Ranked Attractions (base _score) ---")
        for a in kg_atts[:10]:
            feat = a.get("_features", {}) or {}
            print(
                f"{a.get('title','?'):<25} | base={a.get('_score', 0.0):.3f} | "
                f"eco={feat.get('eco_hint', 0.0):.2f} | prox={feat.get('proximity', 0.0):.2f}"
            )
    # ✅ dynamic enrichment + reranking
    # ==========================================================
    # ✅ CITY PLAN ONLY: rerank + NSGA happens ONCE
    # ✅ CORRIDOR PLAN: skip rerank+NSGA (use route_candidates already built)
    # ==========================================================
    dest_pool = []
    route_pool = []
    if not is_corridor_plan:
        # ✅ dynamic enrichment + reranking (RUN ONCE)
        reranked = enrich_and_rerank_candidates(
            candidates=kg_atts,
            payload=payload,
            cfg=EnrichConfig(
                w_sustainability=1.2,
                w_crowd_avoid=0.8,
                w_rain_avoid=0.6,
            ),
            day_offset=0,
        )
        dest_city = str(payload.get("destination") or payload.get("city") or "").strip()
        dest_reranked = [c for c in reranked if _is_destination_candidate(c, dest_city)]
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
        # ✅ NSGA on destination only (RUN ONCE)
        obj_vectors = []
        for i, cand in enumerate(dest_reranked):
            objectives, explain = build_objectives(cand, payload)
            cand["_nsga_objectives"] = objectives
            cand["_nsga_explain"] = explain
            obj_vectors.append((objectives, i))
        front_indices = pareto_front(obj_vectors)
        pareto_dest = [dest_reranked[i] for i in front_indices]
        print("\n--- NSGA-II Pareto Front (DESTINATION ONLY) ---")
        for c in pareto_dest[:10]:
            e = c["_nsga_explain"]
            print(
                f"{c.get('title','?'):<25} | "
                f"match={e['match_0_1']:.2f} sus={e['sustainability_0_1']:.2f} "
                f"crowd={e['crowd_risk_0_1']:.2f} rain={e['rain_risk_0_1']:.2f}"
            )
        dest_pool = pareto_dest
        # ==========================
        # ✅ WAYPOINT (STOP) PIPELINE
        # ==========================
        waypoint_plans = []

        # ==========================
        # ✅ WAYPOINT (STOP) PIPELINE
        # payload example:
        #   waypoints = ["Anuradhapura"]
        #   stop_durations_days = {"Anuradhapura": 2}
        # ==========================
        # ==========================
        # ✅ WAYPOINT (STOP) FULL PLAN (DESTINATION-LIKE)
        # ==========================
        waypoints = payload.get("waypoints") or []
        stop_days_map = payload.get("stop_durations_days") or {}

        per_day = int(payload.get("per_day_attractions") or cfg.per_day_attractions)

        # Choose where the waypoint starts on the calendar:
        # Option A (simple): waypoint starts at trip start_date
        wp_cursor_dt = start_dt

        for wp in waypoints:
            wp_city = str(wp or "").strip()
            if not wp_city:
                continue

            wp_days = int(stop_days_map.get(wp_city) or 1)

            # 1) waypoint pipeline (KG -> rerank -> NSGA)
            wp_out = run_city_pipeline(wp_city, payload, cfg)
            wp_pool = wp_out["pareto_pool"] or []

            # ✅ NEW: distribute ALL NSGA items across wp_days
            wp_days = max(1, int(stop_days_map.get(wp_city) or 1))
            per_day_wp = max(1, math.ceil(len(wp_pool) / wp_days))  # ✅ THIS is the key fix

            wp_itinerary_days = build_itinerary_days_simple_chunk(
                pool=wp_pool,                 # ✅ all NSGA items
                city=wp_city,
                country=country,
                start_dt=wp_cursor_dt,
                days=wp_days,
                per_day=per_day_wp,           # ✅ computed from NSGA count
                eco_pref=eco_pref,
                explicit_city_for_enrich=wp_city,
            )

            waypoint_plans.append({
                "status": "ok",
                "plan_type": "waypoint",
                "waypoint_city": wp_city,
                "start_date": wp_cursor_dt.isoformat(),
                "days": wp_days,
                "itinerary": wp_itinerary_days,
                "debug": {
                    "pareto_count": len(wp_pool),
                    "per_day_waypoint": per_day_wp,
                    "kg_dbg": wp_out.get("kg_dbg", {}),
                    "allocation": "all_nsga_divided_by_stop_days",
                },
            })

            wp_cursor_dt = wp_cursor_dt + timedelta(days=wp_days)
    else:
        # ✅ corridor plan: NO rerank/NSGA here
        # you already computed route_candidates above
        route_pool = kg_atts
    # ==========================
    # NEW: route anchor coords
    # ==========================
    # ✅ Build itinerary source depending on plan type
    if not is_corridor_plan:
        simple_itinerary = build_itinerary(
            ranked_candidates=dest_pool,
            days=days,
            per_day=int(payload.get("per_day_attractions") or cfg.per_day_attractions),
            anchor=None,
        )
    else:
        # ✅ corridor plan: include ALL filtered route attractions (already sorted origin -> destination)
        # route_pool == route_candidates (kg_mode=corridor_kg_points)
        simple_itinerary = [{
            "day": 1,
            "district": None,
            "attractions": route_pool  # This now contains all 20+ POIs found
        }]
    itinerary_days: List[Dict[str, Any]] = []
    slots = ["morning", "afternoon"]
    for i, day_pack in enumerate(simple_itinerary):
        day_number = int(day_pack.get("day") or (i + 1))
        day_date = start_dt + timedelta(days=day_number - 1)
        day_str = day_date.isoformat()
        day_items: List[Dict[str, Any]] = []
        for idx, a in enumerate(day_pack["attractions"]):
            item_city = a.get("city") or a.get("district") or city
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
                "city": item_city,
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
    warnings.extend(getattr(tm, "assumptions", []) or [])

    # ==========================
    # ✅ HOTEL FETCH for destination city
    # ==========================
    if not payload.get("_hotels"):
        try:
            hotel_items, hotel_dbg = fetch_hotels_for_destination(payload, timeout=15.0)
            payload["_hotels"] = {
                "items": hotel_items,
                "debug": hotel_dbg,
            }
            print(f"\n[HOTELS] Fetched {len(hotel_items)} hotels for destination='{city}'")
        except Exception as exc:
            payload["_hotels"] = {
                "items": [],
                "debug": {"error": str(exc)},
            }
            warnings.append(f"Hotel fetch failed: {exc}")
            print(f"[HOTELS] Error: {exc}")

    return {
        "status": "ok",
        "city": city,
        "country": country,
        "start_date": start_dt.isoformat(),
        "days": days,
        "travel_mode_used": tm.__dict__,
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
        "hotels": payload.get("_hotels") or {},
        "shopping_dining_on_route": payload.get("_shopping_dining_on_route") or {},
        "waypoint_plans": waypoint_plans,
        "way_out_stop_plans": payload.get("_way_out_stop_plans") or [],
        "debug": {
            "route_anchor_coords": route_start_coords,
            "kg_mode": kg_mode,
            # (optional but useful) expose that we attempted OD preflight
            "kg_od_preflight_ok": bool(payload.get("_od_preflight")),
            "kg_od_preflight_error": payload.get("_od_preflight_error"),
            "route_distance_m": distance_m,
            "route_time_ms": time_ms,
            "graphhopper_sampled_points": sampled_points,
        }
    }