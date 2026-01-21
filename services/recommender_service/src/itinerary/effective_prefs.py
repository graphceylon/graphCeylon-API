from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class EffectivePrefs:
    hard_filters: Dict[str, Any]
    soft_prefs: Dict[str, Any]
    weights: Dict[str, float]
    sources: Dict[str, str]  # query/db/none


def _get_sources(payload: Dict[str, Any]) -> Dict[str, str]:
    trace = payload.get("trace") or {}
    ps = trace.get("preference_sources") or {}
    # normalize to lowercase strings
    out = {}
    for k, v in ps.items():
        out[k] = str(v or "none").lower()
    return out


def _weight_for_source(source: str) -> float:
    # ✅ your key requirement: query > db
    if source == "query":
        return 1.6
    if source == "db":
        return 1.0
    return 0.6  # none/unknown = weak


def build_effective_prefs(payload: Dict[str, Any]) -> EffectivePrefs:
    sources = _get_sources(payload)

    # -----------------------
    # 1) HARD FILTERS
    # -----------------------
    hard_filters: Dict[str, Any] = {}

    # location is always a hard filter
    hard_filters["city"] = (payload.get("city") or payload.get("destination") or "").strip()

    # explicit diet constraint: only veg/vegan
    food = payload.get("food_preferences") or []
    if isinstance(food, list):
        food_l = [str(x).lower() for x in food]
        if "vegetarian" in food_l or "vegan" in food_l:
            hard_filters["diet"] = "veg_only"

    # budget constraint can be hard OR soft depending on query
    max_budget = payload.get("max_trip_budget_lkr")
    if max_budget is not None:
        hard_filters["max_trip_budget_lkr"] = int(max_budget)

    # -----------------------
    # 2) SOFT PREFS (optimize)
    # -----------------------
    soft_prefs: Dict[str, Any] = {}
    for key in [
        "travel_style",
        "tags",
        "eco_preference",
        "temperature_preference",
        "rain_preference",
        "avoid_crowds",
        "pace_preference",
        "adventure_level",
        "preferred_transport",
        "budget_level",
    ]:
        v = payload.get(key)
        if v is not None:
            soft_prefs[key] = v

    # -----------------------
    # 3) WEIGHTS (boost if query)
    # -----------------------
    weights: Dict[str, float] = {}
    for key in soft_prefs.keys():
        src = sources.get(key, "none")
        weights[key] = _weight_for_source(src)

    return EffectivePrefs(
        hard_filters=hard_filters,
        soft_prefs=soft_prefs,
        weights=weights,
        sources=sources,
    )
