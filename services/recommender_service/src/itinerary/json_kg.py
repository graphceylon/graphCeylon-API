from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional


# ----------------------------
# Load KG (JSON)
# ----------------------------

DEFAULT_KG_PATH = Path(
    #"/Users/dev/Desktop/graphCeylon-API/data/recommender_service/clean/kg/attractions_clean.json"
    "C:/Users/HP/OneDrive/Documents/graphCeylon-API/data/recommender_service/clean/kg/attractions_clean.json"
)

def load_attractions_json(path: Path = DEFAULT_KG_PATH) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("attractions"), list):
        return [x for x in raw["attractions"] if isinstance(x, dict)]
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    return []


# ----------------------------
# Preference sources -> weights
# ----------------------------

def _get_pref_sources(payload: Dict[str, Any]) -> Dict[str, str]:
    trace = payload.get("trace") or {}
    ps = trace.get("preference_sources") or {}
    return {k: str(v or "none").lower() for k, v in ps.items()}

def _src_weight(src: str) -> float:
    # ✅ query gets more priority than db
    if src == "query":
        return 1.6
    if src == "db":
        return 1.0
    return 0.6  # none/unknown

def _infer_src_for_field(payload: Dict[str, Any], sources: Dict[str, str], field: str) -> str:
    """
    If trace doesn't include a field (like tags/types), infer source:
    - if payload has non-empty value -> query
    - else -> none
    """
    if field in sources:
        return sources[field]
    v = payload.get(field)
    if isinstance(v, list) and len(v) > 0:
        return "query"
    if isinstance(v, str) and v.strip():
        return "query"
    return "none"


# ----------------------------
# Matching helpers
# ----------------------------

def _norm(s: Any) -> str:
    return str(s or "").strip().lower()

def _normalize_text_for_match(s: Any) -> str:
    s = _norm(s)
    s = re.sub(r"[-_]+", " ", s)       # eco-friendly -> eco friendly
    s = re.sub(r"\s+", " ", s).strip() # collapse spaces
    return s

def _as_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i) for i in x if str(i).strip()]
    if isinstance(x, str) and x.strip():
        return [x.strip()]
    return []

def _norm_list(x: Any) -> List[str]:
    return [_normalize_text_for_match(v) for v in _as_list(x) if _normalize_text_for_match(v)]

def _text_blob(rec: Dict[str, Any]) -> str:
    return " ".join([
        _normalize_text_for_match(rec.get("title")),
        _normalize_text_for_match(rec.get("description")),
        _normalize_text_for_match(rec.get("district")),
        _normalize_text_for_match(rec.get("province")),
        _normalize_text_for_match(rec.get("attraction_id")),
    ])

# Map abstract styles to terms likely present in your JSON descriptions
STYLE_SYNONYMS: Dict[str, List[str]] = {
    "culture": ["culture", "cultural", "buddhist", "temple", "monastery", "heritage", "festival", "traditional"],
    "history": ["history", "historical", "heritage", "ancient", "ruins", "museum", "king", "kingdom", "archaeological"],
    "family": ["family", "kids", "children", "park", "zoo", "garden", "lake"],
    "outdoor": ["outdoor", "trail", "hike", "trek", "mountain", "forest", "park", "river", "waterfall"],
    "eco": ["eco", "nature", "forest", "reserve", "sanctuary", "wildlife", "national park", "botanical", "lake"],
}
def _place_match_score(name_n: str, rec: Dict[str, Any]) -> int:
    """
    Higher = better match. Uses district/province/title/description.
    """
    fields = ["district", "province", "city", "title", "description"]
    score = 0
    for f in fields:
        v = _normalize_text_for_match(rec.get(f))
        if not v:
            continue
        # exact contains match gets higher
        if name_n == v:
            score += 5
        elif name_n in v:
            score += 3
    return score


def resolve_place_coords_from_kg(
    place_name: Any,
    attractions: List[Dict[str, Any]],
    *,
    min_hits: int = 8,
) -> Optional[Tuple[float, float]]:
    name_n = _normalize_text_for_match(place_name)
    if not name_n:
        return None

    # optional fallback
    if name_n in CITY_COORDS:
        return CITY_COORDS[name_n]

    scored: List[Tuple[int, float, float]] = []
    for rec in attractions:
        lat, lng = rec.get("lat"), rec.get("lng")
        if lat is None or lng is None:
            continue
        s = _place_match_score(name_n, rec)
        if s <= 0:
            continue
        try:
            scored.append((s, float(lat), float(lng)))
        except Exception:
            continue

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)

    top = scored[:max(min_hits, min(len(scored), 25))]

    if len(top) < min_hits and top[0][0] < 3:
        return None

    lat_avg = sum(x[1] for x in top) / len(top)
    lng_avg = sum(x[2] for x in top) / len(top)
    return (lat_avg, lng_avg)

def _to_xy_km(lat: float, lon: float, ref_lat: float) -> Tuple[float, float]:
    # Equirectangular approximation (fast, good enough for SL)
    x = lon * 111.320 * math.cos(math.radians(ref_lat))
    y = lat * 110.574
    return x, y
def _is_origin_or_dest(rec: Dict[str, Any], origin_name: Any, dest_name: Any) -> bool:
    o = _normalize_text_for_match(origin_name)
    d = _normalize_text_for_match(dest_name)

    rid = _normalize_text_for_match(rec.get("attraction_id"))
    title = _normalize_text_for_match(rec.get("title"))
    district = _normalize_text_for_match(rec.get("district"))
    city = _normalize_text_for_match(rec.get("city"))

    # match if the record is literally the city node/entry
    def _match(name: str) -> bool:
        if not name:
            return False
        return (
            name == rid
            or name == title
            or name == district
            or name == city
            or title == name
        )

    # Always exclude origin. Destination exclusion is optional (see below).
    return _match(o) or False

def _dist_point_to_segment_km(px, py, ax, ay, bx, by) -> float:
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx * abx + aby * aby
    if ab2 == 0:
        return math.hypot(apx, apy)

    t = (apx * abx + apy * aby) / ab2
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * abx, ay + t * aby
    return math.hypot(px - cx, py - cy)

def _filter_by_corridor(
    recs: List[Dict[str, Any]],
    origin: Tuple[float, float],
    dest: Tuple[float, float],
    corridor_km: float,
) -> List[Dict[str, Any]]:
    o_lat, o_lng = origin
    d_lat, d_lng = dest
    ref_lat = (o_lat + d_lat) / 2.0

    ax, ay = _to_xy_km(o_lat, o_lng, ref_lat)
    bx, by = _to_xy_km(d_lat, d_lng, ref_lat)

    out = []
    for rec in recs:
        lat, lng = rec.get("lat"), rec.get("lng")
        if lat is None or lng is None:
            continue
        try:
            px, py = _to_xy_km(float(lat), float(lng), ref_lat)
        except Exception:
            continue

        dist = _dist_point_to_segment_km(px, py, ax, ay, bx, by)
        if dist <= corridor_km:
            r2 = dict(rec)
            r2["_corridor_km"] = float(dist)
            out.append(r2)

    return out


def _expand_keywords(keywords: List[str]) -> List[str]:
    """
    Expand keywords with synonyms (for better text matching).
    Keeps order, removes duplicates.
    """
    out: List[str] = []
    for k in keywords or []:
        kn = _normalize_text_for_match(k)
        if not kn:
            continue
        out.append(kn)
        if kn in STYLE_SYNONYMS:
            out.extend(STYLE_SYNONYMS[kn])

    seen = set()
    uniq: List[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq

def _keyword_match_score(blob: str, keywords: List[str]) -> float:
    """
    Return [0..1] = fraction of keywords/phrases found in blob.
    Handles phrases and partial token fallback.
    """
    if not keywords:
        return 0.0

    blob_n = _normalize_text_for_match(blob)
    hits = 0
    total = 0

    for k in keywords:
        k = _normalize_text_for_match(k)
        if not k:
            continue
        total += 1

        # phrase / substring
        if k in blob_n:
            hits += 1
            continue

        # fallback: token presence
        toks = [t for t in k.split(" ") if t]
        if toks and any(t in blob_n for t in toks):
            hits += 1

    return 0.0 if total == 0 else min(1.0, hits / total)

def _eco_hint(blob: str, travel_style: List[str]) -> float:
    """
    Lightweight eco-ness hint from description text.
    """
    blob_n = _normalize_text_for_match(blob)
    eco_terms = [
        "eco", "nature", "forest", "park", "reserve", "botanical",
        "lake", "sanctuary", "trail", "hike", "wildlife",
        "waterfall", "river", "mountain", "garden"
    ]
    hits = sum(1 for w in eco_terms if w in blob_n)
    score = min(1.0, hits / 6.0)  # ~6 hits => max

    ts_n = " ".join(_normalize_text_for_match(x) for x in (travel_style or []))
    if any(w in ts_n for w in ["eco", "nature", "hike", "wildlife", "outdoor"]):
        score = max(score, 0.6)

    return max(0.05, min(1.0, score))

def _type_match_score(wanted: List[str], rec_types: List[str]) -> float:
    """
    wanted: desired types/tags (normalized)
    rec_types: record types (normalized)
    score: [0..1] overlap ratio
    """
    if not wanted or not rec_types:
        return 0.0
    w = set(wanted)
    r = set(rec_types)
    overlap = len(w.intersection(r))
    return min(1.0, overlap / max(1, len(w)))


# ----------------------------
# Proximity helpers (Haversine)
# ----------------------------

CITY_COORDS: Dict[str, Tuple[float, float]] = {
    "kandy": (7.2906, 80.6337),
    "colombo": (6.9271, 79.8612),
    "galle": (6.0535, 80.2210),
    "negombo": (7.2055, 79.8513),
    "nuwara eliya": (6.9607, 80.7693),
    "trincomalee": (8.5874, 81.2152),
    "sigiriya": (7.9568, 80.7603),
    "dambulla": (7.8567, 80.6499),
}

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

def _anchor_coords_from_payload(payload: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """
    Resolve anchor coords in priority order:
    1) payload["city_lat"], payload["city_lng"]
    2) payload["lat"], payload["lng"]
    3) CITY_COORDS lookup from city/destination
    """
    for a, b in [("city_lat", "city_lng"), ("lat", "lng")]:
        if payload.get(a) is not None and payload.get(b) is not None:
            try:
                return (float(payload[a]), float(payload[b]))
            except Exception:
                pass

    city = _normalize_text_for_match(payload.get("city") or payload.get("destination") or "")
    return CITY_COORDS.get(city)
def resolve_region_anchor_from_districts(
    payload: Dict[str, Any],
    attractions: List[Dict[str, Any]],
) -> Optional[Tuple[float, float]]:
    geo = payload.get("geo_scope") or {}
    if geo.get("mode") != "region":
        return None

    districts = geo.get("districts") or []
    coords: List[Tuple[float, float]] = []

    for d in districts:
        dn = _normalize_text_for_match(d)
        if not dn:
            continue

        # 1) try KG-based resolution
        c = resolve_place_coords_from_kg(dn, attractions)

        # 2) fallback to CITY_COORDS if KG didn't resolve
        if c is None:
            c = CITY_COORDS.get(dn)

        if c is not None:
            coords.append(c)

    if not coords:
        return None

    lat = sum(x[0] for x in coords) / len(coords)
    lng = sum(x[1] for x in coords) / len(coords)
    return (lat, lng)

def _distance_score(distance_km: float, radius_km: float) -> float:
    """
    Convert distance to [0..1] score: closer = higher.
    - 0km => 1.0
    - radius_km => 0.0
    """
    if distance_km <= 0:
        return 1.0
    if distance_km >= radius_km:
        return 0.0
    return max(0.0, 1.0 - (distance_km / radius_km))
def _apply_geo_scope_filter(payload: Dict[str, Any], recs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    geo = payload.get("geo_scope") or {}
    if geo.get("mode") != "region":
        return recs

    allowed = geo.get("districts") or []
    if not allowed:
        return recs

    out = []
    for r in recs:
        if _district_match(str(r.get("district") or ""), allowed):
            out.append(r)
    return out


# ----------------------------
# Query from JSON KG
# ----------------------------

@dataclass
class KGQueryResult:
    candidates: List[Dict[str, Any]]
    debug: Dict[str, Any]
def _district_match(rec_district: str, allowed_districts: List[str]) -> bool:
    rd = _normalize_text_for_match(rec_district)
    if not rd:
        return False

    for a in allowed_districts:
        a = _normalize_text_for_match(a)
        if not a:
            continue

        # exact
        if rd == a:
            return True

        # contains either way (handles "badulla district", "nuwara-eliya")
        if a in rd or rd in a:
            return True

        # common suffix
        if rd.replace(" district", "").strip() == a:
            return True

    return False

def query_attractions_from_json(
    payload: Dict[str, Any],
    *,
    kg_path: Path = DEFAULT_KG_PATH,
    limit: int = 120,
    prefilter_limit: int = 300,
    radius_km: float = 25.0,
    use_radius_filter: bool = True,
    mode: str = "local",          # "local" or "corridor"
    corridor_km: float = 15.0,
) -> KGQueryResult:

    print(">>> JSON-KG QUERY VERSION: 2026-01-02-v6 (KG-resolve + corridor) <<<")

    city = payload.get("city") or payload.get("region") or payload.get("destination") or ""

    travel_style = _as_list(payload.get("travel_style"))
    tags = _as_list(payload.get("tags"))

    travel_style_expanded = _expand_keywords([str(x) for x in travel_style])
    tags_expanded = _expand_keywords([str(x) for x in tags])

    eco_pref = payload.get("eco_preference")
    eco_pref = float(eco_pref) if eco_pref is not None else 0.5

    sources = _get_pref_sources(payload)
    w_travel = _src_weight(_infer_src_for_field(payload, sources, "travel_style"))
    w_tags   = _src_weight(_infer_src_for_field(payload, sources, "tags"))
    w_eco    = _src_weight(_infer_src_for_field(payload, sources, "eco_preference"))

    # weights
    w_prox = 1.3
    w_type = 2.0
    w_corridor = 0.7  # corridor closeness bonus

    all_atts = load_attractions_json(kg_path)

# ✅ NEW: apply region scope filtering if present (Hill Country, South, etc.)
    all_atts = _apply_geo_scope_filter(payload, all_atts)
    origin_name = payload.get("origin_city") or payload.get("origin")
    dest_name   = payload.get("city") or payload.get("destination")  # default "destination" unless city exists

    origin_coords: Optional[Tuple[float, float]] = None
    dest_coords: Optional[Tuple[float, float]] = None
    anchor: Optional[Tuple[float, float]] = None


    geo = payload.get("geo_scope") or {}
    if geo.get("mode") == "region":
        use_radius_filter = False
        radius_km = 100.0   # optional safety


    # 1) compute coords if names exist
    if origin_name:
        origin_coords = resolve_place_coords_from_kg(origin_name, all_atts)

    if dest_name:
        dest_coords = resolve_place_coords_from_kg(dest_name, all_atts)

    # 2) region mode => anchor should be centroid of districts
    region_anchor = resolve_region_anchor_from_districts(payload, all_atts)

    if geo.get("mode") == "region" and region_anchor is not None:
        anchor = region_anchor
    else:
        # normal local anchor around destination
        anchor = dest_coords



    filtered: List[Dict[str, Any]] = []

    # ---- Prefilter strategy ----
    if mode == "corridor" and origin_coords and dest_coords:
        # Day-1 style: between origin and destination
        corridor_hits = _filter_by_corridor(all_atts, origin_coords, dest_coords, corridor_km)
        filtered = corridor_hits[:]
        if not filtered:
            filtered = [dict(x) for x in all_atts[:]]
    else:
        # Local mode (existing behavior): radius around destination anchor if possible
        if anchor:
            a_lat, a_lng = anchor
            for rec in all_atts:
                lat = rec.get("lat")
                lng = rec.get("lng")
                if lat is None or lng is None:
                    continue
                try:
                    dkm = _haversine_km(a_lat, a_lng, float(lat), float(lng))
                except Exception:
                    continue

                if (not use_radius_filter) or (dkm <= radius_km):
                    r2 = dict(rec)
                    r2["_distance_km"] = float(dkm)
                    filtered.append(r2)

            if not filtered:
                filtered = [dict(x) for x in all_atts[:]]
        else:
            # No anchor => fallback to city text contains
            c = _normalize_text_for_match(city)

            def _contains_city(rec: Dict[str, Any]) -> bool:
                if not c:
                    return True
                for k in ("district", "province", "title", "description"):
                    if c in _normalize_text_for_match(rec.get(k)):
                        return True
                return False

            filtered = [dict(a) for a in all_atts if _contains_city(a)]
            if not filtered:
                filtered = [dict(x) for x in all_atts[:]]

    filtered = filtered[:prefilter_limit]

    wanted_types = _norm_list(travel_style) + _norm_list(tags)

    scored: List[Tuple[float, Dict[str, Any]]] = []
    for rec in filtered:
        blob = _text_blob(rec)

        match_ts = _keyword_match_score(blob, travel_style_expanded)
        match_tags = _keyword_match_score(blob, tags_expanded)

        eco = _eco_hint(blob, travel_style)

        # proximity (local mode uses distance_km)
        if anchor and rec.get("_distance_km") is not None:
            prox = _distance_score(float(rec["_distance_km"]), radius_km)
        else:
            prox = 0.3

        # type matching (if your JSON includes "types")
        rec_types_raw = rec.get("types") or rec.get("type") or []
        rec_types = _norm_list(rec_types_raw)
        type_score = _type_match_score(wanted_types, rec_types)

        # corridor bonus (corridor mode uses _corridor_km)
        corridor_bonus = 0.0
        if mode == "corridor" and rec.get("_corridor_km") is not None:
            corridor_bonus = max(0.0, 1.0 - (float(rec["_corridor_km"]) / corridor_km))

        score = (
            (w_type * type_score)
            + (w_travel * match_ts)
            + (w_tags * match_tags)
            + (w_eco * (eco_pref * eco))
            + (w_prox * prox)
            + (w_corridor * corridor_bonus)
        )

        out = dict(rec)
        out["_score"] = float(score)
        out["_features"] = {
            "type_score": float(type_score),
            "wanted_types": wanted_types,
            "rec_types": rec_types,
            "match_travel_style": float(match_ts),
            "match_tags": float(match_tags),
            "eco_hint": float(eco),
            "eco_preference": float(eco_pref),
            "proximity": float(prox),
            "distance_km": float(out.get("_distance_km", -1.0)) if anchor else -1.0,
            "corridor_km": float(out.get("_corridor_km", -1.0)) if mode == "corridor" else -1.0,
            "corridor_bonus": float(corridor_bonus),
        }
        out["_weights"] = {
            "w_type": float(w_type),
            "w_travel_style": float(w_travel),
            "w_tags": float(w_tags),
            "w_eco": float(w_eco),
            "w_proximity": float(w_prox),
            "w_corridor": float(w_corridor),
        }

        scored.append((score, out))

    scored.sort(key=lambda x: x[0], reverse=True)
    geo = payload.get("geo_scope") or {}
    if geo.get("mode") == "region":
        allowed = [_normalize_text_for_match(d) for d in (geo.get("districts") or [])]
        k_per_district = max(5, limit // max(1, len(allowed)))

        buckets: Dict[str, List[Dict[str, Any]]] = {d: [] for d in allowed}
        rest: List[Dict[str, Any]] = []

        for _, rec in scored:
            d = _normalize_text_for_match(rec.get("district"))
            if d in buckets and len(buckets[d]) < k_per_district:
                buckets[d].append(rec)
            else:
                rest.append(rec)

        merged: List[Dict[str, Any]] = []
        for d in allowed:
            merged.extend(buckets[d])

        seen_ids = set(_normalize_text_for_match(x.get("attraction_id")) for x in merged)
        for rec in rest:
            rid = _normalize_text_for_match(rec.get("attraction_id"))
            if rid and rid in seen_ids:
                continue
            merged.append(rec)
            if len(merged) >= limit:
                break

        top = merged[:limit]
    else:
        top = [r for _, r in scored[:limit]]


    debug = {
        "kg_path": str(kg_path),
        "mode": mode,
        "city_filter": city,
        "origin_name": origin_name,
        "dest_name": dest_name,
        "origin_coords": origin_coords,
        "dest_coords": dest_coords,
        "anchor_coords": anchor,
        "radius_km": radius_km,
        "corridor_km": corridor_km,
        "total_loaded": len(all_atts),
        "prefiltered": len(filtered),
        "returned": len(top),
        "preference_sources": sources,
        "weights_used": {
            "type": w_type,
            "travel_style": w_travel,
            "tags": w_tags,
            "eco_preference": w_eco,
            "proximity": w_prox,
            "corridor": w_corridor,
        },
    }

    return KGQueryResult(candidates=top, debug=debug)



# ----------------------------
# Optional: pretty print helper
# ----------------------------

def print_top_candidates(res: KGQueryResult, n: int = 10) -> None:
    print("\n================ JSON-KG TOP CANDIDATES ================")
    for r in res.candidates[:n]:
        f = r.get("_features", {})
        print(
            f"{r.get('title','?'):<32} | "
            f"score={r.get('_score',0.0):.3f} | "
            f"type={f.get('type_score',0.0):.2f} | "
            f"eco={f.get('eco_hint',0.0):.2f} | "
            f"prox={f.get('proximity',0.0):.2f} | "
            f"dist={f.get('distance_km',-1.0):.1f}km | "
            f"types={(f.get('rec_types',[])[:4])}"
        )
    print("========================================================\n")
