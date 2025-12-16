# src/recommendation/test_json_kg_client.py

from pprint import pprint

from .json_kg_client import JsonKGClient


def test_manual_intent_payload():
    """
    This test lets you manually paste the JSON you get from the orchestrator
    (intent parser) and see which attractions are selected from
    tourist_attractions.json via JsonKGClient.
    """

    client = JsonKGClient()

    # 👇 PASTE YOUR ORCHESTRATOR JSON HERE
    payload = {
        "user_id": "nimal_001",
        "session_id": "sess_2025_002",
        "lang": "en",
        "channel": "chat",
        
        "intent": "recommend_pois",
        "secondary_intents": ["crowd_forecast"],
        
        "entities": {
            "city": "Nuwara Eliya",
            "region": "Central Province",
            "country": "Sri Lanka",
        
            "poi_name": "",
            "activity_type": "attraction",
        
            "start_date": "null",
            "end_date": "null",
            "travel_month": "null",
            "days": "weekend",
        
            "time_of_day": "afternoon",
        
            "num_travelers": 1,
            "travel_with": "null",
        
            "origin": "null",
            "destination": "null",
        
            "budget_level": "null",
        
            "tags": ["nature"]
        },
        
        "preference_overrides": {
            "travel_style": ["nature"],
            "avoid_crowds": "true",
            "budget_level": "null",
            "eco_preference": "null",
            "accessibility_needs": "null",
            "food_preferences": [],
            "preferred_transport": [],
            "sun_sensitivity": "null",
            "rain_preference": "null",
            "temperature_preference": "null",
            "avoid_stray_animals": "null",
            "motion_sickness": "null"
        },
    }

    entities = payload["entities"]
    prefs = payload.get("preference_overrides", {})

    city = entities.get("city")
    tags = entities.get("tags") or []
    travel_style = prefs.get("travel_style") or []

    # We’ll treat tags + travel_style as "categories" for now
    # e.g. ["nature", "culture"]
    categories = list({*(tags or []), *(travel_style or [])})

    print("=== Orchestrator payload ===")
    print(f"City from intent      : {city}")
    print(f"Tags from entities    : {tags}")
    print(f"Travel style overrides: {travel_style}")
    print(f"Combined categories   : {categories}")
    print()

    # 🔗 This is the key line:
    # We map city -> region (district) because in your data
    # Kandy's district is also "Kandy".
    # JsonKGClient.get_attractions() uses:
    #   region -> p.district
    #   categories -> p.categories
    results = client.get_attractions(city=city)


    print("=== Matching attractions from tourist_attractions.json ===")
    print(f"Total matches: {len(results)}")
    print()

    for a in results:
        pprint(
            {
                "id": a.id,
                "name": a.name,
                "district": a.district,
                "lat": a.lat,
                "lon": a.lon,
                "categories": a.categories,
                "tags": a.tags,
                "base_price_lkr": a.base_price_lkr,
                "avg_visit_hours": a.avg_visit_hours,
            }
        )
        print("-" * 60)


if __name__ == "__main__":
    test_manual_intent_payload()
