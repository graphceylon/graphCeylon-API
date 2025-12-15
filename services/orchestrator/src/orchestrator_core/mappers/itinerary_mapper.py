from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.itinerary import ItineraryPlanRequest


def map_itinerary_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> ItineraryPlanRequest:
    e = parsed_intent.entities
    p = parsed_intent.preference_overrides

    # If days isn’t extracted yet, keep it None (service can default)
    days = e.days

    # destination: city or country fallback
    destination = e.city or e.country

    return ItineraryPlanRequest(
        intent="plan_itinerary",
        user_id=req.user_id,
        session_id=req.session_id,
        raw_text=req.input_text,
        city=e.city,
        country=e.country,
        start_date=e.start_date,
        end_date=e.end_date,
        time_of_day=e.time_of_day,
        days=days,
        origin=e.origin,
        destination=destination,
        travel_style=p.travel_style or [],
        budget_level=p.budget_level,
        avoid_crowds=p.avoid_crowds,
    )
