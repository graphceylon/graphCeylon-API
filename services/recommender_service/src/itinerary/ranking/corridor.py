from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional
import math

# re-use your JSON KG loader + place resolver + scoring query
from ..json_kg import (
    load_attractions_json,
    resolve_place_coords_from_kg,
    query_attractions_from_json,
)

def _to_xy_km(lat: float, lon: float, ref_lat: float) -> Tuple[float, float]:
    # Equirectangular approximation (fast enough for Sri Lanka)
    x = lon * 111.320 * math.cos(math.radians(ref_lat))
    y = lat * 110.574
    return x, y

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

    out: List[Dict[str, Any]] = []
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

def query_attractions_along_route(
    payload: Dict[str, Any],
    *,
    origin_city: Optional[str] = None,
    destination_city: Optional[str] = None,
    corridor_km: float = 15.0,
) :
    """
    Returns KGQueryResult but filtered to a 'route corridor' (origin -> destination).
    - Uses KG itself to resolve origin/destination coords (not static)
    - Falls back to normal local query if coords can't be resolved
    """

    all_atts = load_attractions_json()

    origin_name = origin_city or payload.get("origin_city") or payload.get("origin")
    dest_name = destination_city or payload.get("destination") or payload.get("city")

    origin_coords = resolve_place_coords_from_kg(origin_name, all_atts) if origin_name else None
    dest_coords   = resolve_place_coords_from_kg(dest_name, all_atts) if dest_name else None

    # If we can't resolve both ends, fallback to normal city query
    if not origin_coords or not dest_coords:
        return query_attractions_from_json(payload, mode="local")

    # First: get broad candidates without radius filter
    base = query_attractions_from_json(payload, mode="local", use_radius_filter=False)

    # Then: corridor filter
    corridor_candidates = _filter_by_corridor(base.candidates, origin_coords, dest_coords, corridor_km)

    # Return same result format
    base.debug["mode"] = "corridor"
    base.debug["origin_coords"] = origin_coords
    base.debug["dest_coords"] = dest_coords
    base.debug["corridor_km"] = corridor_km
    base.debug["corridor_filtered"] = len(corridor_candidates)

    return type(base)(candidates=corridor_candidates, debug=base.debug)
