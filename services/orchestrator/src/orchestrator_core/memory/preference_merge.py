# services/orchestrator/src/orchestrator_core/memory/preference_merge.py
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, Literal

Source = Literal["query", "db", "none"]

PREFERENCE_KEYS = {
    "travel_style",
    "eco_preference",
    "avoid_crowds",
    "food_preferences",
    "activity_preference",
    "pace_preference",
    "adventure_level",
    "budget_level",
    "budget_per_night_lkr",
    "budget_flexibility",
    "preferred_transport",
    "accessibility_needs",
    "walking_tolerance_minutes",
    "accommodation_type",
    "star_preference",
    "must_have_amenities",
    "cancellation_preference",
    "sun_sensitivity",
    "rain_preference",
    "temperature_preference",
    "motion_sickness",
}

def _is_present(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    if isinstance(v, (list, tuple, set, dict)):
        return len(v) > 0
    return True

def merge_preferences(
    db_prefs: Optional[Dict[str, Any]],
    query_overrides: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Source]]:
    """
    Returns:
      merged_prefs: effective preferences (query wins)
      pref_source:  per-field source of the final value ("query" | "db" | "none")
    """
    base = dict(db_prefs or {})
    q = dict(query_overrides or {})

    base = {k: v for k, v in base.items() if k in PREFERENCE_KEYS}
    q = {k: v for k, v in q.items() if k in PREFERENCE_KEYS}

    merged: Dict[str, Any] = {}
    source: Dict[str, Source] = {}

    for k in PREFERENCE_KEYS:
        q_has = k in q and _is_present(q.get(k))
        db_has = k in base and _is_present(base.get(k))

        if q_has:
            merged[k] = q[k]
            source[k] = "query"
        elif db_has:
            merged[k] = base[k]
            source[k] = "db"
        else:
            source[k] = "none"

    # keep created_at/schema_version if present in query or db (optional)
    if "created_at" in q:
        merged["created_at"] = q["created_at"]
    elif "created_at" in base:
        merged["created_at"] = base["created_at"]

    if "schema_version" in q:
        merged["schema_version"] = q["schema_version"]
    elif "schema_version" in base:
        merged["schema_version"] = base["schema_version"]

    return merged, source
