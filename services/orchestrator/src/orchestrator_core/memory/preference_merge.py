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

# values that should NOT override DB prefs when coming from query
_STR_NOT_PRESENT = {"", "unknown", "any", "n/a", "none", "null"}

def _is_present(v: Any) -> bool:
    """
    True only when v is meaningful enough to override.
    Prevents query placeholders like "unknown"/"any" from overwriting DB values.
    """
    if v is None:
        return False

    if isinstance(v, str):
        s = v.strip().lower()
        return s not in _STR_NOT_PRESENT

    if isinstance(v, (list, tuple, set, dict)):
        return len(v) > 0

    return True


def merge_preferences(
    db_prefs: Optional[Dict[str, Any]],
    query_overrides: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Source]]:
    """
    Returns:
      merged_prefs: effective preferences (query wins when meaningful)
      pref_source:  per-field source of the final value ("query" | "db" | "none")
    """
    # keep unfiltered originals so we can carry metadata like created_at/schema_version
    base_all = dict(db_prefs or {})
    q_all = dict(query_overrides or {})

    # Only merge the preference keys
    base = {k: v for k, v in base_all.items() if k in PREFERENCE_KEYS}
    q = {k: v for k, v in q_all.items() if k in PREFERENCE_KEYS}

    merged: Dict[str, Any] = {}
    source: Dict[str, Source] = {}

    for k in PREFERENCE_KEYS:
        q_has = _is_present(q.get(k)) if k in q else False
        db_has = _is_present(base.get(k)) if k in base else False

        if q_has:
            merged[k] = q[k]
            source[k] = "query"
        elif db_has:
            merged[k] = base[k]
            source[k] = "db"
        else:
            source[k] = "none"

    # keep created_at/schema_version if present in query or db (optional)
    if "created_at" in q_all and _is_present(q_all.get("created_at")):
        merged["created_at"] = q_all["created_at"]
    elif "created_at" in base_all and _is_present(base_all.get("created_at")):
        merged["created_at"] = base_all["created_at"]

    if "schema_version" in q_all and _is_present(q_all.get("schema_version")):
        merged["schema_version"] = q_all["schema_version"]
    elif "schema_version" in base_all and _is_present(base_all.get("schema_version")):
        merged["schema_version"] = base_all["schema_version"]

    return merged, source
