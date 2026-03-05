from ..contracts.book_hotel import BookHotelRequest
from ...api.schemas import ParsedIntent, OrchestrateRequest


def map_book_hotel_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> BookHotelRequest:
    entities = parsed_intent.entities
    prefs = parsed_intent.preference_overrides

    # ✅ support both arrival/departure (edit context) and start_date/end_date (classifier)
    arrival = (
        getattr(entities, "arrival", None)
        or getattr(entities, "start_date", None)
        or getattr(entities, "check_in", None)
    )
    departure = (
        getattr(entities, "departure", None)
        or getattr(entities, "end_date", None)
        or getattr(entities, "check_out", None)
    )

    trace = {
        "session_id": req.session_id,
        "user_id": req.user_id,
    }

    if getattr(entities, "max_price_lkr", None) is not None:
        trace["max_price_lkr"] = entities.max_price_lkr
    elif getattr(prefs, "budget_per_night_lkr", None) is not None:
        trace["budget_per_night_lkr"] = prefs.budget_per_night_lkr

    # ✅ pass room selections through so book_hotel_flow uses them instead of defaults
    return BookHotelRequest(
        city=getattr(entities, "city", None),
        arrival=str(arrival) if arrival else None,
        departure=str(departure) if departure else None,
        adults=int(getattr(entities, "adults", None) or getattr(entities, "num_travelers", None) or 2),
        room_category_id=getattr(entities, "room_category_id", None),
        room_type_id=getattr(entities, "room_type_id", None),
        meal_plan_id=getattr(entities, "meal_plan_id", None),
        rate_code_id=getattr(entities, "rate_code_id", None),
        property_id=getattr(entities, "property_id", None),
        property_code=getattr(entities, "property_code", None),
        trace=trace,
    )