from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.itinerary_modify import ItineraryModifyRequest
from ..utils.pref_access import pref_get


def map_itinerary_modify_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> ItineraryModifyRequest:
    e = parsed_intent.entities
    p = parsed_intent.preference_overrides

    raw_text = getattr(req, "text", None) or getattr(req, "input_text", "") or ""

    # ✅ These will be injected by orchestrator for same-session modify
    itinerary_id = pref_get(e, "itinerary_id")
    current_itinerary = pref_get(e, "current_itinerary")

    # Prefer override budget_level, fallback to entity-extracted budget_level
    budget_level = pref_get(p, "budget_level") or pref_get(e, "budget_level")

    return ItineraryModifyRequest(
        user_id=req.user_id,
        session_id=req.session_id,
        raw_text=raw_text,

        itinerary_id=itinerary_id,                 # ✅ now filled
        current_itinerary=current_itinerary,       # ✅ now filled

        modification_text=raw_text,

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