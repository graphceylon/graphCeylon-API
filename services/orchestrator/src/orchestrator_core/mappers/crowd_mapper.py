# crowd_mapper.py
from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.crowd import CrowdForecastRequest

def map_crowd_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> CrowdForecastRequest:
    e = parsed_intent.entities

    # ✅ Crowd service needs a POI id/name.
    # If poi_name isn't extracted, fall back to city (e.g., "Colombo").
    poi_name = (e.poi_name or e.city or "").strip() or None

    return CrowdForecastRequest(
        intent="crowd_forecast",
        user_id=req.user_id,
        session_id=req.session_id,
        raw_text=req.input_text,
        country=e.country,
        city=e.city,
        poi_name=poi_name,           
        start_date=e.start_date,
        end_date=e.end_date,
        time_of_day=e.time_of_day,
    )