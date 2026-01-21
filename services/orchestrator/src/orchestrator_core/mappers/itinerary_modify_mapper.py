from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.itinerary_modify import ItineraryModifyRequest
from ..utils.pref_access import pref_get


def map_itinerary_modify_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> ItineraryModifyRequest:
    e = parsed_intent.entities
    p = parsed_intent.preference_overrides

    # If you later store itinerary_id in session/db, you can fetch it here.
    itinerary_id = None

    # Prefer override budget_level, fallback to entity-extracted budget_level
    budget_level = pref_get(p, "budget_level") or pref_get(e, "budget_level")

    return ItineraryModifyRequest(
        user_id=req.user_id,
        session_id=req.session_id,

        # Use whichever field you actually have in OrchestrateRequest
        raw_text=getattr(req, "text", None) or getattr(req, "input_text", ""),

        itinerary_id=itinerary_id,
        current_itinerary=None,

        modification_text=getattr(req, "text", None) or getattr(req, "input_text", ""),

        start_date=pref_get(e, "start_date"),
        end_date=pref_get(e, "end_date"),
        days=pref_get(e, "days"),

        budget_level=budget_level,
        avoid_crowds=bool(pref_get(p, "avoid_crowds") or False),
        travel_style=pref_get(p, "travel_style") or [],

        city=pref_get(e, "city"),
        poi_name=pref_get(e, "poi_name"),
        country=pref_get(e, "country"),
    )
