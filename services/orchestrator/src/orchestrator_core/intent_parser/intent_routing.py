# orchestrator_core/intent_parser/intent_routing.py

from typing import Dict

# LOGICAL OWNER for each intent
# (These are "agents" in the orchestration sense; some may map to the same backend service.)

INTENT_TO_AGENT: Dict[str, str] = {
    # ---- Component 3: Recommendation & Sustainability Service ----
    # These hit /itinerary, /recommend, /forecast, etc.
    "plan_itinerary": "RecommendationService",
    "recommend_pois": "RecommendationService",
    "modify_itinerary": "RecommendationService",
    "crowd_forecast": "RecommendationService",

    # ---- Other domain agents / services ----
    "info_attraction": "AttractionsAgent",       # KG / attractions service
    "info_accommodation": "HotelAgent",
    "info_transport": "TransportAgent",
    "info_visa_policy": "VisaPolicyAgent",
    "update_preferences": "ProfileAgent",
    "explanation_request": "ExplainabilityAgent",
    "generic_fact_query": "KnowledgeAgent",      # or FallbackAgent / LLM
}

# What high-level ACTION each intent triggers.
# Your TaskExecutor will later map these to specific HTTP calls/endpoints.
INTENT_TO_ACTION: Dict[str, str] = {
    # ---- Recommendation Service endpoints ----
    "plan_itinerary": "call_rec_itinerary",          # -> POST /itinerary
    "recommend_pois": "call_rec_recommend",          # -> POST /recommend
    "modify_itinerary": "call_rec_modify_itinerary", # -> POST /itinerary/modify (or similar)
    "crowd_forecast": "call_rec_forecast",           # -> POST /forecast

    # ---- Attractions / Hotels / Other Agents ----
    "info_attraction": "call_info_attraction",       # -> AttractionsAgent (KG-first)
    "info_accommodation": "call_info_accommodation", # -> HotelAgent
    "info_transport": "call_info_transport",         # -> TransportAgent
    "info_visa_policy": "call_visa_policy",
    "update_preferences": "update_user_preferences",
    "explanation_request": "generate_explanation",
    "generic_fact_query": "answer_fact_query",
}
