# src/kg/json_client.py
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from .client_base import AttractionKGClient
from .models import Attraction

class JsonKGClient(AttractionKGClient):
    def __init__(self, sltda_json_path: str, manual_features_path: Optional[str] = None):
        data = json.loads(Path(sltda_json_path).read_text(encoding="utf-8"))
        self._raw_attractions = data["attractions"]

        # index of manual features by some key (place_id / id / title)
        self._manual_by_key: Dict[str, Dict[str, Any]] = {}

        if manual_features_path:
            raw_manual = json.loads(
                Path(manual_features_path).read_text(encoding="utf-8")
            )

            # Case 1: already a dict keyed by id / place_id
            if isinstance(raw_manual, dict):
                self._manual_by_key = raw_manual

            # Case 2: list of feature objects -> build an index
            elif isinstance(raw_manual, list):
                idx: Dict[str, Dict[str, Any]] = {}
                for item in raw_manual:
                    key = (
                        item.get("place_id")
                        or item.get("id")
                        or item.get("slug")
                        or item.get("title")
                    )
                    if key:
                        idx[key] = item
                self._manual_by_key = idx

            # else: leave empty dict

        self._attractions = [self._to_attraction(raw) for raw in self._raw_attractions]

    def _to_attraction(self, raw) -> Attraction:
        admin = raw["geolocation"]["address_info"]["administrative_areas"]
        coords = raw["geolocation"]["coordinates"]
        place_id = raw["geolocation"]["geocoding_metadata"]["place_id"]
        title = raw["title"]

        # try lookup by place_id first, then by title
        features = (
            self._manual_by_key.get(place_id)
            or self._manual_by_key.get(title)
            or {}
        )

        return Attraction(
            id=features.get("id", place_id),  # stable ID if you defined one, else place_id
            name=raw["title"],
            description=raw.get("description", ""),

            country=admin["country"],
            province=admin["province"],
            district=admin["district"],
            city=admin["city"] or admin["district"],

            latitude=coords["latitude"],
            longitude=coords["longitude"],

            image_url=raw.get("image_url"),
            price_level=raw.get("google_place_data", {}).get("price_level"),
            place_types=raw.get("google_place_data", {}).get("place_types", []),
            tags=features.get("tags", []),
            google_place_id=place_id,
        )

    def search_attractions(
        self,
        city: Optional[str] = None,
        region: Optional[str] = None,
        country: Optional[str] = None,
        poi_name: Optional[str] = None,
        tags: Optional[list[str]] = None,
        activity_type: Optional[str] = None,
        budget_level: Optional[str] = None,
    ) -> List[Attraction]:
        results = self._attractions

        if country:
            c = country.lower()
            results = [a for a in results if a.country.lower() == c]

        if city:
            c = city.lower()
            results = [a for a in results if a.city and a.city.lower() == c]

        if region:
            r = region.lower()
            results = [
                a for a in results
                if a.province and a.province.lower() == r
                or a.district and a.district.lower() == r
            ]

        if poi_name:
            n = poi_name.lower()
            results = [a for a in results if n in a.name.lower()]

        if tags:
            tag_set = {t.lower() for t in tags}
            results = [
                a for a in results
                if a.tags and tag_set.intersection(t.lower() for t in a.tags)
            ]

        # budget_level/activity_type handling can be added later
        return results

    def get_attraction_by_id(self, attraction_id: str) -> Optional[Attraction]:
        return next((a for a in self._attractions if a.id == attraction_id), None)
