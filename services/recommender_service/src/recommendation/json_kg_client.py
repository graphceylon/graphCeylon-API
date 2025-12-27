# src/recommendation/json_kg_client.py
import json
from pathlib import Path
from typing import List, Optional

from .kg_client import KGClient
from .attraction_model import Attraction

# This file is at:
#   .../Proactive-Tourism-Recommendation/component3_service/src/recommendation/json_kg_client.py
# parents[0] -> /recommendation
# parents[1] -> /src
# parents[2] -> /component3_service
# parents[3] -> /Proactive-Tourism-Recommendation  (project root)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = Path(__file__).resolve().parents[2]

# JSON from your message:
# C:\Users\HP\OneDrive\Documents\Proactive-Tourism-Recommendation\datasets\kg
ATTRACTIONS_JSON = PROJECT_ROOT / "datasets" / "kg" / "tourist_attractions.json"

# Keep features inside component3_service (as you originally planned)
FEATURES_JSON = SERVICE_ROOT / "data_static" / "attraction_features_manual.json"
# This will store:
#   id, categories, tags, base_price_lkr, avg_visit_hours,
#   eco_sensitivity, capacity_score, popularity_score


class JsonKGClient(KGClient):
    def __init__(self):
        # Debug print so you can see exactly what paths are being used
        print("[JsonKGClient] ATTRACTIONS_JSON:", ATTRACTIONS_JSON)
        print("[JsonKGClient] FEATURES_JSON   :", FEATURES_JSON)

        # --- Load attractions (required) ---
        if not ATTRACTIONS_JSON.exists():
            raise FileNotFoundError(
                f"[JsonKGClient] tourist_attractions.json not found at: {ATTRACTIONS_JSON}"
            )

        with open(ATTRACTIONS_JSON, "r", encoding="utf-8") as f:
            self.raw = json.load(f)

        # --- Load features (optional for now) ---
        if FEATURES_JSON.exists():
            with open(FEATURES_JSON, "r", encoding="utf-8") as f:
                feature_list = json.load(f)

            self.features_by_title = {
                f["title"].strip().lower(): f for f in feature_list
            }
        else:
            print(
                "[JsonKGClient] WARNING: attraction_features_manual.json not found. "
                "Using fallback defaults for categories/prices/etc."
            )
            self.features_by_title = {}

        self._attractions = self._build_attractions()

    def _build_attractions(self) -> List[Attraction]:
        attractions: List[Attraction] = []

        for a in self.raw.get("attractions", []):
            title = a.get("title", "").strip()
            if not title:
                continue

            feat = self.features_by_title.get(title.lower())

            admin = a.get("geolocation", {}).get("address_info", {}).get(
                "administrative_areas", {}
            )
            coords = a.get("geolocation", {}).get("coordinates", {})
            map_links = a.get("geolocation", {}).get("map_links", {})
            map_url = map_links.get("google_maps_url")

            province = admin.get("province", "Unknown")   # 👈 NEW
            district = admin.get("district", "Unknown")
            city = admin.get("city", "") or district    

            if feat is not None:
                categories = feat.get("categories", [])
                tags = feat.get("tags", [])
                base_price_lkr = feat.get("base_price_lkr", 0.0)
                avg_visit_hours = feat.get("avg_visit_hours", 2.0)
                eco_sensitivity = feat.get("eco_sensitivity", 0.5)
                capacity_score = feat.get("capacity_score", 0.5)
                popularity_score = feat.get("popularity_score", 0.5)
                attr_id = feat.get("id", title.upper().replace(" ", "_"))
            else:
                categories = ["general"]
                tags = []
                base_price_lkr = 0.0
                avg_visit_hours = 2.0
                eco_sensitivity = 0.5
                capacity_score = 0.5
                popularity_score = 0.5
                attr_id = title.upper().replace(" ", "_")

            attractions.append(
                Attraction(
                    id=attr_id,
                    name=title,
                    district=district,
                    city=city, 
                    province=province,                # 👈 store city here
                    lat=coords.get("latitude"),
                    lon=coords.get("longitude"),
                    categories=categories,
                    tags=tags,
                    base_price_lkr=base_price_lkr,
                    avg_visit_hours=avg_visit_hours,
                    eco_sensitivity=eco_sensitivity,
                    capacity_score=capacity_score,
                    popularity_score=popularity_score,
                    image_url=a.get("image_url"),
                    map_url=map_url,
                )
            )

        print(f"[JsonKGClient] Built {len(attractions)} Attraction objects")
        return attractions


    def get_attractions(
        self,
        region: Optional[str] = None,      # orchestrator.entities.region -> province
        city: Optional[str] = None,        # orchestrator.entities.city
        categories: Optional[list[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Attraction]:
        results = self._attractions

        # ✅ 1. If city is provided, use city/district dual matching
        if city:
            c = city.strip().lower()
            results = [
                p for p in results
                if (
                    (p.city and p.city.lower() == c) or
                    (p.district and p.district.lower() == c)
                )
            ]

        # ✅ 2. Else, if region is provided, treat it as province
        elif region:
            r = region.strip().lower()
            results = [
                p for p in results
                if (p.province and p.province.lower() == r)
            ]

        # ✅ 3. Optional category filtering (can be softened as we discussed)
        if categories:
            cats = {c.lower() for c in categories}
            results = [
                p
                for p in results
                if any(c.lower() in cats for c in (p.categories or []))
            ]

        if limit is not None:
            results = results[:limit]

        return results
