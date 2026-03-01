from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional, Tuple
import json

LatLon = Tuple[float, float]  # (lat, lon)

_CITY_INDEX: Optional[Dict[str, LatLon]] = None

def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def load_city_index(cities_json_path: Path) -> Dict[str, LatLon]:
    global _CITY_INDEX
    if _CITY_INDEX is not None:
        return _CITY_INDEX

    raw = json.loads(cities_json_path.read_text(encoding="utf-8"))
    idx: Dict[str, LatLon] = {}

    for c in raw.get("cities", []):
        name = _norm(str(c.get("city") or ""))
        lat = c.get("latitude")
        lng = c.get("longitude")
        if name and lat is not None and lng is not None:
            try:
                idx[name] = (float(lat), float(lng))
            except Exception:
                pass

    _CITY_INDEX = idx
    return idx

def resolve_city_coords(city: str, *, cities_json_path: Path) -> Optional[LatLon]:
    if not city:
        return None
    idx = load_city_index(cities_json_path)
    return idx.get(_norm(city))