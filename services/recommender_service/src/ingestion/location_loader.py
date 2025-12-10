import json
from typing import List, Dict
from pathlib import Path

from configs.recommender_service.config import KG_ATTRACTIONS_FILE


def _slugify(text: str) -> str:
    """Create a simple, stable id from the title (e.g. 'Anuradhapura' -> 'anuradhapura')."""
    return (
        text.strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("'", "")
    )


def load_locations_from_kg(max_locations: int | None = None) -> List[Dict]:
    """
    Load attraction locations from the KG JSON:
    {
      "total_attractions": ...,
      "scrape_metadata": {...},
      "attractions": [
        {
          "title": "...",
          "geolocation": {
            "coordinates": {
              "latitude": ...,
              "longitude": ...
            }
          },
          ...
        },
        ...
      ]
    }

    Returns a list of dicts with keys: id, name, lat, lon
    """
    path: Path = KG_ATTRACTIONS_FILE

    if not path.exists():
        raise FileNotFoundError(f"KG attractions file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Expect top-level dict with "attractions" list
    attractions = data.get("attractions", [])
    if not isinstance(attractions, list):
        raise TypeError(
            f"Expected 'attractions' to be a list in {path}, got {type(attractions)}"
        )

    locations: List[Dict] = []

    for node in attractions:
        title = node.get("title")
        geo = (node.get("geolocation") or {}).get("coordinates") or {}
        lat = geo.get("latitude")
        lon = geo.get("longitude")

        if title is None or lat is None or lon is None:
            # Skip incomplete entries; you can log if needed
            continue

        loc_id = _slugify(title)

        locations.append(
            {
                "id": loc_id,        # e.g. "anuradhapura"
                "name": title,       # e.g. "Anuradhapura"
                "lat": float(lat),
                "lon": float(lon),
            }
        )

        if max_locations is not None and len(locations) >= max_locations:
            break

    if not locations:
        raise ValueError(
            f"No valid locations found in KG file {path}. "
            f"Check 'title' and geolocation.coordinates.latitude/longitude fields."
        )

    return locations
