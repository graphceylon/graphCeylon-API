from __future__ import annotations

from typing import Dict, Any, Optional, List
import json
from pathlib import Path
import re


def _find_repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / "data").exists() and (parent / "services").exists():
            return parent
    # fallback
    return p.parents[5]


def _iter_records(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, dict):
        if isinstance(obj.get("attractions"), list):
            return [x for x in obj["attractions"] if isinstance(x, dict)]
        if isinstance(obj.get("restaurants"), list):
            return [x for x in obj["restaurants"] if isinstance(x, dict)]
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    return []


def load_attractions_index() -> Dict[str, Dict[str, Any]]:
    """
    Build a lookup index for normalization:
      - keys: attraction_id, poi_id, id, slug, title/name (lowercased)
      - values: full record from attractions_clean.json
    """
    repo_root = _find_repo_root()
    path = repo_root / "data" / "recommender_service" / "clean" / "kg" / "attractions_clean.json"
    if not path.exists():
        raise FileNotFoundError(f"attractions_clean.json not found at: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    records = _iter_records(raw)

    index: Dict[str, Dict[str, Any]] = {}

    for r in records:
        aid = str(r.get("attraction_id") or r.get("poi_id") or r.get("id") or "").strip()
        if not aid:
            continue

        # normalize canonical id
        r2 = dict(r)
        r2["attraction_id"] = str(r.get("attraction_id") or aid).strip()

        keys = set()

        for k in ("attraction_id", "poi_id", "id", "slug"):
            if r.get(k):
                keys.add(str(r[k]).strip().lower())

        for k in ("title", "name"):
            if r.get(k):
                keys.add(str(r[k]).strip().lower())

        # include canonical id too
        keys.add(r2["attraction_id"].strip().lower())

        for key in keys:
            index[key] = r2

    return index


ATTRACTION_INDEX = load_attractions_index()

def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-")

def normalize_to_attraction_id(raw: Any) -> Optional[str]:
    """
    Accepts:
      - str: "Temple of the Tooth" -> "temple-of-the-tooth"
      - dict: {"name": "..."} or {"id": "..."} etc.
      - other: stringifies safely
    """
    if raw is None:
        return None

    # ✅ raw is already a string
    if isinstance(raw, str):
        s = raw

    # ✅ raw is dict-like
    elif isinstance(raw, dict):
        s = None
        for k in ("attraction_id", "id", "poi_id", "name", "title", "poi_name"):
            v = raw.get(k)
            if isinstance(v, str) and v.strip():
                s = v
                break
        if s is None:
            s = str(raw)

    else:
        s = str(raw)

    s = s.strip()
    if not s:
        return None
    return _slug(s)


def get_attraction_record(attraction_id: str) -> Optional[Dict[str, Any]]:
    if not attraction_id:
        return None
    rec = ATTRACTION_INDEX.get(str(attraction_id).strip().lower())
    return dict(rec) if rec else None
