# src/db/test_user_preferences_repo.py

from sqlalchemy.orm import Session

from src.db.session import SessionLocal
from src.db.repositories.user_preferences_repo import (
    get_user_preferences_by_user_id,
    upsert_user_preferences_from_questionnaire,
    create_user_preferences,
)



def main():
    db: Session = SessionLocal()

    try:
        user_id = "nimal_001"

        questionnaire_data = {
            "home_country": "Sri Lanka",
            "is_international": False,
            "age": 30,
            "traveller_type": "solo",
            "food_type": "non_veg",
            "diet_restrictions": ["no_pork"],
            "weather_pref": "avoid_hot",
            "crowd_tolerance": "avoid_crowds",
            "mobility_needs": "none",
            "budget_level": "mid",
            # NSGA-II preference vector
            "pref_vector": {
                "nature": 0.9,
                "culture": 0.7,
                "nightlife": 0.1,
                "shopping": 0.3,
                "beach": 0.5,
            },
        }

        print("Upserting user preferences for:", user_id)
        prefs = upsert_user_preferences_from_questionnaire(
            db, user_id=user_id, questionnaire_data=questionnaire_data
        )
        print("Saved preferences id:", prefs.id)

        # Fetch back and print
        fetched = get_user_preferences_by_user_id(db, user_id)
        print("\nFetched preferences:")
        print(" user_id          :", fetched.user_id)
        print(" country_of_origin:", fetched.country_of_origin)
        print(" is_domestic      :", fetched.is_domestic)
        print(" age              :", fetched.age)
        print(" travel_pace      :", fetched.travel_pace)
        print(" diet_type        :", fetched.diet_type)
        print(" food_preferences :", fetched.food_preferences)
        print(" temperature_pref :", fetched.temperature_preference)
        print(" crowd_tolerance  :", fetched.crowd_tolerance)
        print(" budget_level     :", fetched.budget_level)
        print(" pref_vector      :", fetched.pref_vector)

    finally:
        db.close()


if __name__ == "__main__":
    main()
