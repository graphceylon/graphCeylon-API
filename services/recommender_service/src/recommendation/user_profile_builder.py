# src/recommendation/user_profile_builder.py

from typing import Any, Dict

from sqlalchemy.orm import Session

from src.db.repositories.user_preferences_repo import (
    get_user_preferences_by_user_id,
)
from src.recommendation.user_profile import UserProfile


def build_user_profile(payload: Dict[str, Any], db: Session) -> UserProfile:
    """
    Build a runtime UserProfile by combining:
      - long-term preferences stored in Postgres (UserPreference)
      - current request overrides from Orchestrator payload
    """
    user_id = payload.get("user_id", "anonymous")
    entities = payload.get("entities") or {}
    overrides = payload.get("preference_overrides") or {}

    # ---- 1. Load stored preferences from Postgres (if any) ----
    row = get_user_preferences_by_user_id(db, user_id)

    if row is not None:
        tag_weights: Dict[str, float] = {}

        # convert pref_vector JSONB into lowercase float map
        if row.pref_vector:
            for k, v in row.pref_vector.items():
                try:
                    tag_weights[str(k).lower()] = float(v)
                except (TypeError, ValueError):
                    continue

        profile = UserProfile(
            user_id=row.user_id,
            username=row.username,
            age=row.age,
            country_of_origin=row.country_of_origin,
            is_domestic=row.is_domestic,
            tag_weights=tag_weights,
            budget_level=row.budget_level,
            sun_sensitivity=row.sun_sensitivity,
            rain_preference=row.rain_preference,
            temperature_preference=row.temperature_preference,
            crowd_tolerance=row.crowd_tolerance,
            diet_type=row.diet_type,
            food_preferences=row.food_preferences or [],
            accessibility_needs=row.accessibility_needs,
            preferred_transport=row.preferred_transport or [],
            avoid_stray_animals=row.avoid_stray_animals,
            motion_sickness=row.motion_sickness,
        )
    else:
        # no stored row → start from neutral profile
        profile = UserProfile(user_id=user_id)

    # ---- 2. Apply per-request overrides from Orchestrator ----

    # a) travel_style + entities.tags -> boost tag_weights
    travel_style = overrides.get("travel_style") or []
    entity_tags = entities.get("tags") or []

    for t in travel_style + entity_tags:
        key = str(t).lower()
        current = profile.tag_weights.get(key, 0.0)
        # higher of existing vs override boost
        profile.tag_weights[key] = max(current, 0.85)

    # b) avoid_crowds (explicit override or derived from crowd_tolerance)
    avoid_crowds_override = overrides.get("avoid_crowds")
    if avoid_crowds_override is not None:
        profile.avoid_crowds = bool(avoid_crowds_override)
    else:
        if profile.crowd_tolerance in ("low", "avoid_crowds"):
            profile.avoid_crowds = True

    # c) budget override (if provided in payload)
    if overrides.get("budget_level"):
        profile.budget_level = overrides["budget_level"]

    # d) optional weather & accessibility overrides (you can expand later)
    if overrides.get("sun_sensitivity"):
        profile.sun_sensitivity = overrides["sun_sensitivity"]

    if overrides.get("rain_preference"):
        profile.rain_preference = overrides["rain_preference"]

    if overrides.get("temperature_preference"):
        profile.temperature_preference = overrides["temperature_preference"]

    if overrides.get("accessibility_needs"):
        profile.accessibility_needs = overrides["accessibility_needs"]

    if overrides.get("preferred_transport"):
        profile.preferred_transport = overrides["preferred_transport"]

    if overrides.get("avoid_stray_animals") is not None:
        profile.avoid_stray_animals = bool(overrides["avoid_stray_animals"])

    if overrides.get("motion_sickness") is not None:
        profile.motion_sickness = bool(overrides["motion_sickness"])

    return profile
