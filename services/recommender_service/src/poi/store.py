import json
from pathlib import Path
from typing import List
from math import radians, sin, cos, sqrt, atan2

from .schema import POI

SERVICE_ROOT = Path(__file__).resolve().parents[4]  # graphCeylon-API root
DATA_PATH = SERVICE_ROOT / "data" / "recommender_service" / "clean" / "kg" / "attractions_clean.json"

def _norm(s: str) -> str:
    return "".join(ch.lower() for ch in s if ch.isalnum() or ch.isspace()).strip()


def _resolve_anchor_from_json(pois: List[POI], base_query: str) -> tuple[float, float]:
    q = _norm(base_query)

    # 1️⃣ title match
    for p in pois:
        if _norm(p.title) == q:
            return p.lat, p.lng

    # 2️⃣ attraction_id match
    for p in pois:
        if _norm(p.poi_id) == q:
            return p.lat, p.lng

    # 3️⃣ district centroid
    district_hits = [p for p in pois if _norm(p.district) == q]
    if district_hits:
        return (
            sum(p.lat for p in district_hits) / len(district_hits),
            sum(p.lng for p in district_hits) / len(district_hits)
        )

    # 4️⃣ province centroid
    province_hits = [p for p in pois if _norm(p.province) == q]
    if province_hits:
        return (
            sum(p.lat for p in province_hits) / len(province_hits),
            sum(p.lng for p in province_hits) / len(province_hits)
        )

    # ❌ nothing matched
    raise ValueError(
        f"'{base_query}' not found as title, district, province, or attraction_id"
    )


# -------- distance helper --------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))

# -------- load all POIs once --------
def load_pois() -> List[POI]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))["attractions"]
    pois = []
    for r in raw:
        pois.append(POI(
            poi_id=r["attraction_id"],
            title=r["title"],
            lat=r["lat"],
            lng=r["lng"],
            district=r["district"],
            province=r["province"],
            description=r.get("description", "")
        ))
    return pois

# -------- filter by base city radius --------
def get_pois_near_city(base_query: str, radius_km: float = 70) -> List[POI]:
    pois = load_pois()
    base_lat, base_lng = _resolve_anchor_from_json(pois, base_query)

    nearby = []
    for p in pois:
        if haversine_km(base_lat, base_lng, p.lat, p.lng) <= radius_km:
            nearby.append(p)

    return sorted(nearby, key=lambda p: haversine_km(base_lat, base_lng, p.lat, p.lng))
