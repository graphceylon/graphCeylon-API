import json
from pathlib import Path
from typing import List
from math import radians, sin, cos, sqrt, atan2

from .schema import POI

DATA_PATH = Path("data/recommender_service/clean/attractions_clean.json")

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
def get_pois_near_city(base_city: str, radius_km: float = 70) -> List[POI]:
    pois = load_pois()

    base = next(p for p in pois if p.title.lower() == base_city.lower())

    nearby = []
    for p in pois:
        d = haversine_km(base.lat, base.lng, p.lat, p.lng)
        if d <= radius_km:
            nearby.append(p)

    return nearby
