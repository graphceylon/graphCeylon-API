# src/orchestrator_core/mappers/accommodation_mapper.py
from src.api.schemas import ParsedIntent, OrchestrateRequest
from src.orchestrator_core.contracts.accommodation import AccommodationSearchRequest


def map_accommodation_request(
    parsed: ParsedIntent,
    incoming: OrchestrateRequest,
) -> AccommodationSearchRequest:
    e = parsed.entities

    # preference_overrides may be a dict (after your merge) or pydantic model
    prefs = parsed.preference_overrides
    if hasattr(prefs, "model_dump"):
        prefs = prefs.model_dump(exclude_none=True)
    prefs = prefs or {}

    return AccommodationSearchRequest(
        intent=parsed.intent,
        raw_text=parsed.raw_text or incoming.input_text,
        user_id=incoming.user_id,
        session_id=incoming.session_id,

        city=e.city,
        country=e.country or "Sri Lanka",

        min_star_rating=e.min_star_rating,
        max_star_rating=e.max_star_rating,
        must_have_amenities=prefs.get("must_have_amenities", []) or [],
        max_price_lkr=e.max_price_lkr,

        limit=10,
        trace={
            "domain_category": parsed.domain_category,
        }
    )
