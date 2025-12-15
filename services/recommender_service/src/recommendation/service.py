# src/recommendation/service.py

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from src.recommendation.json_kg_client import JsonKGClient
from src.recommendation.user_profile_builder import build_user_profile
from src.recommendation.user_profile import UserProfile
from src.recommendation.attraction_model import Attraction


def recommend_pois_from_payload(payload: Dict[str, Any], db: Session) -> List[Dict[str, Any]]:
    """
    Main entrypoint for the Recommendation Engine.

    - Accepts Orchestrator payload (JSON)
    - Fetches candidate attractions from the JSON KG client
    - Loads user's preferences from Postgres and builds a UserProfile

    For now, it returns candidates along with basic user preference info
    so you can verify the pipeline end-to-end.
    """
    entities = payload.get("entities") or {}
    overrides = payload.get("preference_overrides") or {}

    # ---- 1. Build UserProfile from DB + overrides ----
    user: UserProfile = build_user_profile(payload, db)

    # ---- 2. Fetch candidate attractions from KG ----
    city = entities.get("city")
    categories = overrides.get("travel_style") or []

    kg_client = JsonKGClient()
    candidates: List[Attraction] = kg_client.get_attractions(
        city=city,
        categories=None,
    )

    # ---- 3. (Later) scoring + ranking will go here ----

    response: List[Dict[str, Any]] = []
    for a in candidates:
        response.append(
            {
                "id": a.id,
                "name": a.name,
                "city": a.city,
                "categories": a.categories,
                "tags": a.tags,
                # Debug/user info to verify mapping:
                "user_id": user.user_id,
                "user_budget_level": user.budget_level,
                "user_avoid_crowds": user.avoid_crowds,
                "user_tag_weights": user.tag_weights,
            }
        )

    return response
