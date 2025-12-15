# src/db/repositories/user_preferences_repo.py

from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from src.db.models.user_preferences import UserPreference


def get_user_preferences_by_user_id(
    db: Session,
    user_id: str,
) -> Optional[UserPreference]:
    """
    Fetch a user preferences row by user_id. Returns None if not found.
    """
    return (
        db.query(UserPreference)
        .filter(UserPreference.user_id == user_id)
        .one_or_none()
    )


def create_user_preferences(
    db: Session,
    *,
    user_id: str,
    username: Optional[str] = None,
    age: Optional[int] = None,
    country_of_origin: Optional[str] = None,
    is_domestic: bool = False,
    travel_interests: Optional[List[str]] = None,
    travel_pace: Optional[str] = None,
    destination_types: Optional[List[str]] = None,
    sun_sensitivity: Optional[str] = None,
    rain_preference: Optional[str] = None,
    temperature_preference: Optional[str] = None,
    crowd_tolerance: Optional[str] = None,
    diet_type: Optional[str] = None,
    food_preferences: Optional[List[str]] = None,
    food_strictness: Optional[str] = None,
    budget_level: Optional[str] = None,
    accessibility_needs: Optional[str] = None,
    preferred_transport: Optional[List[str]] = None,
    avoid_stray_animals: bool = False,
    motion_sickness: bool = False,
    pref_vector: Optional[Dict[str, Any]] = None,
) -> UserPreference:
    """
    Create a new user_preferences row.
    """
    prefs = UserPreference(
        user_id=user_id,
        username=username,
        age=age,
        country_of_origin=country_of_origin,
        is_domestic=is_domestic,
        travel_interests=travel_interests or [],
        travel_pace=travel_pace,
        destination_types=destination_types or [],
        sun_sensitivity=sun_sensitivity,
        rain_preference=rain_preference,
        temperature_preference=temperature_preference,
        crowd_tolerance=crowd_tolerance,
        diet_type=diet_type,
        food_preferences=food_preferences or [],
        food_strictness=food_strictness,
        budget_level=budget_level,
        accessibility_needs=accessibility_needs,
        preferred_transport=preferred_transport or [],
        avoid_stray_animals=avoid_stray_animals,
        motion_sickness=motion_sickness,
        pref_vector=pref_vector or {},
    )

    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return prefs


def upsert_user_preferences_from_questionnaire(
    db: Session,
    user_id: str,
    questionnaire_data: Dict[str, Any],
) -> UserPreference:
    """
    Insert or update a user preferences row based on questionnaire answers.

    questionnaire_data example:

    {
      "home_country": "India",
      "is_international": True,
      "age": 28,
      "traveller_type": "couple",
      "food_type": "non_veg",
      "diet_restrictions": ["no_pork"],
      "weather_pref": "avoid_hot",
      "crowd_tolerance": "avoid_crowds",
      "mobility_needs": "none",
      "budget_level": "mid",
      "eco_preference": "high",
      "pref_vector": {"nature": 0.9, "culture": 0.8, "nightlife": 0.1}
    }
    """

    prefs = get_user_preferences_by_user_id(db, user_id)

    if prefs is None:
        prefs = UserPreference(user_id=user_id)

    # Map old questionnaire keys -> new model fields
    if "home_country" in questionnaire_data:
        prefs.country_of_origin = questionnaire_data["home_country"]

    if "is_international" in questionnaire_data:
        # internal convention: is_domestic = not is_international
        prefs.is_domestic = not bool(questionnaire_data["is_international"])

    if "age" in questionnaire_data:
        prefs.age = questionnaire_data["age"]

    if "traveller_type" in questionnaire_data:
        # for now just store traveller_type in travel_pace or leave as-is
        prefs.travel_pace = questionnaire_data["traveller_type"]

    if "food_type" in questionnaire_data:
        prefs.diet_type = questionnaire_data["food_type"]

    if "diet_restrictions" in questionnaire_data:
        prefs.food_preferences = questionnaire_data["diet_restrictions"]

    if "weather_pref" in questionnaire_data:
        weather_pref = questionnaire_data["weather_pref"]
        if weather_pref == "avoid_hot":
            prefs.temperature_preference = "cool"
        else:
            prefs.temperature_preference = weather_pref

    if "crowd_tolerance" in questionnaire_data:
        prefs.crowd_tolerance = questionnaire_data["crowd_tolerance"]

    if "mobility_needs" in questionnaire_data:
        prefs.accessibility_needs = questionnaire_data["mobility_needs"]

    if "budget_level" in questionnaire_data:
        prefs.budget_level = questionnaire_data["budget_level"]

    if "pref_vector" in questionnaire_data:
        prefs.pref_vector = questionnaire_data["pref_vector"]

    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return prefs
