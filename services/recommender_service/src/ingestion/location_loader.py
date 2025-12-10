# src/ingestion/location_loader.py

import json
import re
from pathlib import Path
from typing import List, Dict

from src.config import KG_ATTRACTIONS_FILE


def slugify(text: str) -> str:
    """Create a simple ID from the attraction title."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def load_locations_from_kg(max_locations: int | None = None) -> List[Dict]:
    """
    Load attraction locations from the KG JSON file.

    Returns a list of dicts:
      [
        {"id": "anuradhapura", "name": "Anuradhapura", "lat": 8.334985, "lon": 80.4106096},
        ...
      ]
    """
    path: Path = KG_ATTRACTIONS_FILE
    if not path.exists():
        raise FileNotFoundError(f"KG attractions file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    attractions = data.get("attractions", [])
    locations: List[Dict] = []

    for attr in attractions:
        title = attr.get("title")
        geo = attr.get("geolocation", {}) or {}
        coords = geo.get("coordinates", {}) or {}

        lat = coords.get("latitude")
        lon = coords.get("longitude")

        # Skip if anything is missing
        if title is None or lat is None or lon is None:
            continue

        loc_id = slugify(title)
        locations.append(
            {
                "id": loc_id,
                "name": title,
                "lat": float(lat),
                "lon": float(lon),
            }
        )

    # Optionally limit for testing
    if max_locations is not None:
        locations = locations[: max_locations]

    if not locations:
        raise ValueError("No valid locations found in KG attractions JSON.")

    return locations
