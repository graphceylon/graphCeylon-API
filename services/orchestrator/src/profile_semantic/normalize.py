from __future__ import annotations
from typing import Any, Dict, Iterable

SENTINELS = {"unknown", "any", "n/a", "na", "none", ""}

def is_present(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip().lower() not in SENTINELS
    if isinstance(v, (list, tuple, set)):
        return len(v) > 0
    if isinstance(v, dict):
        return len(v) > 0
    return True

def clean_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (d or {}).items():
        if isinstance(v, str) and v.strip().lower() in SENTINELS:
            continue
        if isinstance(v, (list, dict)) and len(v) == 0:
            continue
        if v is None:
            continue
        out[k] = v
    return out

def pick(d: Dict[str, Any], keys: Iterable[str]) -> Dict[str, Any]:
    out = {}
    for k in keys:
        if k in d and is_present(d[k]):
            out[k] = d[k]
    return out
