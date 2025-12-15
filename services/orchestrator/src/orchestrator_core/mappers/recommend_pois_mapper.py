from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.recommend_pois import RecommendPOIsRequest


def map_recommend_pois_request(
    parsed_intent: ParsedIntent,
    req: OrchestrateRequest,
) -> RecommendPOIsRequest:
    e = parsed_intent.entities
    prefs = parsed_intent.preference_overrides

    return RecommendPOIsRequest(
        intent="recommend_pois",
        user_id=req.user_id,
        session_id=req.session_id,
        raw_text=req.input_text,
        city=e.city,
        country=e.country,
        start_date=e.start_date,
        end_date=e.end_date,
        tags=e.tags or prefs.travel_style,
        budget_level=prefs.budget_level,
        avoid_crowds=prefs.avoid_crowds,
        eco_preference=prefs.eco_preference,
        num_results=5,
    )
