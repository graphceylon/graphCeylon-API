from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import json

# keep a tiny in-process cache
_CITY_INDEX: Optional[Dict[str, Tuple[float, float]]] = None

def _norm_city(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def _find_repo_root_from(file_path: Path) -> Path:
    p = file_path.resolve()
    for parent in [p] + list(p.parents):
        if (parent / "data").exists() and (parent / "services").exists():
            return parent
    return p.parents[5]

def _load_city_index(repo_root: Path) -> Dict[str, Tuple[float, float]]:
    global _CITY_INDEX
    if _CITY_INDEX is not None:
        return _CITY_INDEX

    cities_path = repo_root / "services" / "recommender_service" / "src" / "routing" / "cities.json"
    raw = json.loads(cities_path.read_text(encoding="utf-8"))

    idx: Dict[str, Tuple[float, float]] = {}
    for c in raw.get("cities", []):
        name = _norm_city(str(c.get("city") or ""))
        lat = c.get("latitude")
        lng = c.get("longitude")
        if name and lat is not None and lng is not None:
            try:
                idx[name] = (float(lat), float(lng))
            except Exception:
                pass

    _CITY_INDEX = idx
    return idx

def resolve_city_coords(
    city: str,
    *,
    repo_root: Path,
) -> Optional[Tuple[float, float]]:
    if not city:
        return None
    idx = _load_city_index(repo_root)
    key = _norm_city(city)
    return idx.get(key)