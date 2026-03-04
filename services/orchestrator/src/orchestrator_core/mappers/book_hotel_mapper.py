from ..contracts.book_hotel import BookHotelRequest
from ...api.schemas import ParsedIntent, OrchestrateRequest


def map_book_hotel_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> BookHotelRequest:
    entities = parsed_intent.entities
    prefs = parsed_intent.preference_overrides

    trace = {
        "session_id": req.session_id,
        "user_id": req.user_id,
    }

    # ✅ Budget priority:
    # 1) max_price_lkr (explicit user query budget)
    # 2) budget_per_night_lkr (long-term DB preference)
    if getattr(entities, "max_price_lkr", None) is not None:
        trace["max_price_lkr"] = entities.max_price_lkr
    elif getattr(prefs, "budget_per_night_lkr", None) is not None:
        trace["budget_per_night_lkr"] = prefs.budget_per_night_lkr

    return BookHotelRequest(
        city=entities.city,
        arrival=str(entities.start_date) if entities.start_date else None,
        departure=str(entities.end_date) if entities.end_date else None,
        adults=int(entities.num_travelers or 2),
        trace=trace,
    )