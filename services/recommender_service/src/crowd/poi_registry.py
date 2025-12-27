from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from services.recommender_service.src.crowd.data.district_norm import norm_district
from pathlib import Path
from configs.recommender_service.config import DATA_CLEAN_DIR
from services.recommender_service.src.crowd.data.district_norm import norm_district

KG_CLEAN_ATTRACTIONS_FILE = DATA_CLEAN_DIR / "kg" / "attractions_clean.json"



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
def pois_by_district(pois: List[POI]) -> Dict[str, List[POI]]:
    out: Dict[str, List[POI]] = {}
    for p in pois:
        if not p.district:
            continue
        key = norm_district(p.district)
        out.setdefault(key, []).append(p)
    return out


def _get_admin_area(item: Dict[str, Any], area_type: str) -> Optional[str]:
    geo = item.get("geolocation", {}) or {}
    addr = geo.get("address_info", {}) or {}
    areas = addr.get("administrative_areas", []) or []
    for a in areas:
        if (a.get("area_type") or "").strip().lower() == area_type.strip().lower():
            return a.get("area_name")
    return None


def _coerce_to_items(raw: Any) -> List[Dict[str, Any]]:
    """
    Accept KG JSON in multiple shapes:
      A) list[dict]  -> OK
      B) list[str]   -> convert each string to {"title": <str>}
      C) dict[...]   -> if values are dicts, take values; if keys are strings, convert to {"title": key}
    """
    # A) list
    if isinstance(raw, list):
        items: List[Dict[str, Any]] = []
        for x in raw:
            if isinstance(x, dict):
                items.append(x)
            elif isinstance(x, str):
                items.append({"title": x})
            else:
                # ignore unknown types
                continue
        return items

    # B) dict
    if isinstance(raw, dict):
        # if values look like dict POIs, use values
        vals = list(raw.values())
        if vals and all(isinstance(v, dict) for v in vals):
            return [v for v in vals if isinstance(v, dict)]
        # otherwise assume keys are POI names
        return [{"title": str(k)} for k in raw.keys()]

    # unknown
    return []


def load_pois(json_path: Path = KG_CLEAN_ATTRACTIONS_FILE) -> List[POI]:
    p = Path(json_path)
    if not p.exists():
        raise FileNotFoundError(f"KG attractions file not found: {p}")

    raw = json.loads(p.read_text(encoding="utf-8"))

    # ✅ handle your cleaned KG format: {"attractions": [ ... ]}
    if isinstance(raw, dict) and isinstance(raw.get("attractions"), list):
        items = raw["attractions"]
    else:
        items = _coerce_to_items(raw)

    pois: List[POI] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        # ✅ prefer stable IDs from KG
        poi_id = (item.get("attraction_id") or item.get("poi_id") or "").strip()
        title = (item.get("title") or item.get("name") or "unknown").strip()

        if not poi_id:
            poi_id = slugify(title)

        # ✅ your cleaned file stores these at top-level
        district = item.get("district")
        province = item.get("province")

        # ✅ your cleaned file uses lat/lng at top-level
        lat = item.get("lat")
        lon = item.get("lng") or item.get("lon")

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
