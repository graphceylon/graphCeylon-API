from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
 # build_attractions_clean.py -> src -> recommender_service -> services -> graphCeylon-API
RAW = REPO_ROOT / "data/recommender_service/raw/kg/tourist_attractions.json"

OUT = Path("data/recommender_service/clean/kg/attractions_clean.json")


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[’']", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _get_title(a: Dict[str, Any]) -> str:
    # fallback title if missing
    title = (a.get("title") or "").strip()
    if title:
        return title

    # try to infer from geolocation address city
    admin = (((a.get("geolocation") or {}).get("address_info") or {}).get("administrative_areas") or {})
    inferred = (admin.get("city") or admin.get("town") or admin.get("village") or "").strip()
    if inferred:
        return inferred

    # last resort
    return "unknown_attraction"


def _get_lat_lng(a: Dict[str, Any]) -> Tuple[float, float]:
    coords = (((a.get("geolocation") or {}).get("coordinates")) or {})
    lat = coords.get("latitude")
    lng = coords.get("longitude")
    if lat is None or lng is None:
        raise ValueError("Missing latitude/longitude")
    return float(lat), float(lng)


def main() -> str:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    raw = json.loads(RAW.read_text(encoding="utf-8"))
    attractions: List[Dict[str, Any]] = raw.get("attractions", [])

    cleaned: List[Dict[str, Any]] = []

    # dedupe key: (place_id) if exists else (rounded lat,lng + normalized title)
    seen = set()

    for a in attractions:
        title = _get_title(a)
        lat, lng = _get_lat_lng(a)

        admin = (((a.get("geolocation") or {}).get("address_info") or {}).get("administrative_areas") or {})
        district = (admin.get("district") or "").strip()
        province = (admin.get("province") or "").strip()

        g = a.get("google_place_data") or {}
        place_id = (((a.get("geolocation") or {}).get("geocoding_metadata") or {}).get("place_id") or "").strip()

        key = None
        if place_id:
            key = ("place_id", place_id)
        else:
            key = ("geo", round(lat, 5), round(lng, 5), slugify(title))

        if key in seen:
            continue
        seen.add(key)

        attraction_id = slugify(title)

        cleaned.append(
            {
                "attraction_id": attraction_id,
                "title": title,
                "lat": lat,
                "lng": lng,
                "district": district,
                "province": province,
                "source": "sltda",
                "place_id": place_id,
                "description": (a.get("description") or "").strip(),
                "image_url": (a.get("image_url") or "").strip(),
                "maps_url": (g.get("place_url") or "").strip(),
            }
        )

    # ensure unique attraction_id (if collisions, append counter)
    used_ids = {}
    for item in cleaned:
        base = item["attraction_id"]
        if base not in used_ids:
            used_ids[base] = 1
        else:
            used_ids[base] += 1
            item["attraction_id"] = f"{base}_{used_ids[base]}"

    OUT.write_text(json.dumps({"attractions": cleaned}, indent=2, ensure_ascii=False), encoding="utf-8")
    return f"✅ wrote {len(cleaned)} attractions to {OUT.as_posix()}"


if __name__ == "__main__":
    print(main())
