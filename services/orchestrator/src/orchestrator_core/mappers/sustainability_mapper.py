from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.sustainability import SustainabilityForecastRequest


def map_sustainability_request(
    parsed_intent: ParsedIntent,
    req: OrchestrateRequest,
) -> SustainabilityForecastRequest:
    e = parsed_intent.entities
    prefs = parsed_intent.preference_overrides

    return SustainabilityForecastRequest(
        intent="forecast_sustainability",
        user_id=req.user_id,
        session_id=req.session_id,
        raw_text=req.input_text,
        city=e.city,
        poi_name=e.poi_name,
        country=e.country,
        start_date=e.start_date,
        end_date=e.end_date,
        eco_preference=prefs.eco_preference,
    )
