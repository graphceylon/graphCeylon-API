from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional
import math
import httpx

# =========================
# CONFIG (safe placeholder)
# =========================
# Replace with your real key locally if you insist.
GRAPHHOPPER_KEY = "0e722598-1d82-4af2-a508-9c515a1e1236"
GRAPHHOPPER_ROUTE_URL = "https://graphhopper.com/api/1/route"


LatLon = Tuple[float, float]  # (lat, lon)


def decode_polyline(encoded: str, precision: int = 5) -> List[LatLon]:
    """Decode encoded polyline -> [(lat, lon), ...]"""
    index, lat, lon = 0, 0, 0
    coordinates: List[LatLon] = []
    factor = 10**precision

    while index < len(encoded):
        shift, result = 0, 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        shift, result = 0, 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlon = ~(result >> 1) if (result & 1) else (result >> 1)
        lon += dlon

        coordinates.append((lat / factor, lon / factor))

    return coordinates


def haversine_km(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    x = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


def downsample_by_distance(points: List[LatLon], step_km: float = 10.0) -> List[LatLon]:
    if not points:
        return []

    out = [points[0]]
    acc = 0.0

    prev = points[0]          # previous point in the full route
    last_kept = points[0]     # last sampled point

    for p in points[1:]:
        # accumulate along the path (prev -> p)
        acc += haversine_km(prev, p)
        prev = p

        if acc >= step_km:
            out.append(p)
            last_kept = p
            acc = 0.0

    if out[-1] != points[-1]:
        out.append(points[-1])

    return out

@dataclass
class RouteResult:
    sampled_points: List[LatLon]
    route_points_count: int
    sampled_points_count: int
    distance_m: Optional[float] = None
    time_ms: Optional[int] = None


def fetch_route_sampled_points(
    origin: LatLon,
    dest: LatLon,
    *,
    profile: str = "car",
    points_encoded: bool = True,
    polyline_precision: int = 5,
    downsample_step_km: float = 10.0,
    timeout: float = 20.0,
) -> RouteResult:
    """
    Calls GraphHopper route API, decodes route polyline, downsamples points.
    origin/dest are (lat, lon).
    Returns sampled points (lat, lon).
    """
    if not GRAPHHOPPER_KEY or GRAPHHOPPER_KEY == "PUT_YOUR_KEY_HERE":
        raise ValueError("GraphHopper key missing. Set GRAPHHOPPER_KEY in graphhopper_route.py")

    url = f"{GRAPHHOPPER_ROUTE_URL}?key={GRAPHHOPPER_KEY}"
    body = {
        "profile": profile,
        "points_encoded": points_encoded,
        "points": [
            [origin[1], origin[0]],  # [lon, lat]
            [dest[1], dest[0]],
        ],
    }

    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=body)
        r.raise_for_status()
        data = r.json()

    paths = data.get("paths") or []
    if not paths:
        return RouteResult(sampled_points=[], route_points_count=0, sampled_points_count=0)

    p0 = paths[0]
    dist_m = p0.get("distance")
    time_ms = p0.get("time")

    points_obj = p0.get("points")

    # points_obj is either:
    # - encoded string (if points_encoded=True)
    # - GeoJSON dict with coordinates (if points_encoded=False)
    route_points: List[LatLon] = []
    if isinstance(points_obj, str):
        route_points = decode_polyline(points_obj, precision=polyline_precision)
    elif isinstance(points_obj, dict):
        coords = points_obj.get("coordinates") or []
        # coords are [lon, lat]
        route_points = [(c[1], c[0]) for c in coords if isinstance(c, list) and len(c) >= 2]

    sampled = downsample_by_distance(route_points, step_km=downsample_step_km)

    return RouteResult(
        sampled_points=sampled,
        route_points_count=len(route_points),
        sampled_points_count=len(sampled),
        distance_m=float(dist_m) if dist_m is not None else None,
        time_ms=int(time_ms) if time_ms is not None else None,
    )