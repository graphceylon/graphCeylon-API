from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from configs.recommender_service.config import KG_ATTRACTIONS_FILE


def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text


@dataclass(frozen=True)
class POI:
    poi_id: str
    title: str
    district: Optional[str]
    province: Optional[str]
    lat: Optional[float]
    lon: Optional[float]


def _get_admin_area(item: Dict[str, Any], area_type: str) -> Optional[str]:
    geo = item.get("geolocation", {}) or {}
    addr = geo.get("address_info", {}) or {}
    areas = addr.get("administrative_areas", []) or []
    for a in areas:
        if (a.get("area_type") or "").strip().lower() == area_type.strip().lower():
            return a.get("area_name")
    return None


def load_pois(json_path: Path = KG_ATTRACTIONS_FILE) -> List[POI]:
    p = Path(json_path)
    if not p.exists():
        raise FileNotFoundError(f"KG attractions file not found: {p}")

    raw = json.loads(p.read_text(encoding="utf-8"))
    pois: List[POI] = []

    for item in raw:
        title = item.get("title") or item.get("name") or "unknown"
        poi_id = slugify(title)

        district = _get_admin_area(item, "District")
        province = _get_admin_area(item, "Province")

        geo = item.get("geolocation", {}) or {}
        coords = geo.get("coordinates", {}) or {}
        lat = coords.get("latitude") or coords.get("lat")
        lon = coords.get("longitude") or coords.get("lng") or coords.get("lon")

        pois.append(
            POI(
                poi_id=poi_id,
                title=title,
                district=(district.strip() if isinstance(district, str) else district),
                province=(province.strip() if isinstance(province, str) else province),
                lat=float(lat) if lat is not None else None,
                lon=float(lon) if lon is not None else None,
            )
        )

    return pois


def pois_by_district(pois: List[POI]) -> Dict[str, List[POI]]:
    out: Dict[str, List[POI]] = {}
    for p in pois:
        if not p.district:
            continue
        key = p.district.strip().lower()
        out.setdefault(key, []).append(p)
    return out
