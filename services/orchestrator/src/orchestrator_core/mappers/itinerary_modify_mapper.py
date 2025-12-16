from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.itinerary_modify import ItineraryModifyRequest

def map_itinerary_modify_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> ItineraryModifyRequest:
    e = parsed_intent.entities
    p = parsed_intent.preference_overrides

    # If you later store itinerary_id in session/db, you can fetch it here.
    itinerary_id = None

    return ItineraryModifyRequest(
        user_id=req.user_id,
        session_id=req.session_id,
        raw_text=req.input_text,

        itinerary_id=itinerary_id,
        current_itinerary=None,  # (optional) fill if you keep it in memory

        modification_text=req.input_text,  # simplest: whole user text as instructions

        start_date=e.start_date,
        end_date=e.end_date,
        days=e.days,

        budget_level=p.budget_level or e.budget_level,
        avoid_crowds=p.avoid_crowds,
        travel_style=p.travel_style or [],

        city=e.city,
        poi_name=e.poi_name,
        country=e.country,
    )
