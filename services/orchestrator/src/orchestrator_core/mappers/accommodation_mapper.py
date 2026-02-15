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

    # ---- FIX: only hard-filter amenities if user explicitly asked in the query ----
    # Try to read a preference source map from ParsedIntent (preferred), else trace.
    src_map = getattr(parsed, "preference_sources", None)
    if src_map is None:
        src_map = (getattr(parsed, "trace", None) or {}).get("preference_sources", {})
    if src_map is None:
        src_map = {}

    amenities = prefs.get("must_have_amenities", None)

    # Distinguish None vs []:
    # - None => not provided by query/overrides (could exist in DB)
    # - []   => explicitly "no amenities filter"
    if amenities is None:
        amenities = []

    # If amenities didn't come from query, do NOT apply as hard filter.
    # This prevents DB defaults like ["wifi","ac"] from causing "No matches".
    if src_map.get("must_have_amenities") != "query":
        amenities = []
    # ------------------------------------------------------------------------------

    return AccommodationSearchRequest(
        intent=parsed.intent,
        raw_text=parsed.raw_text or incoming.input_text,
        user_id=incoming.user_id,
        session_id=incoming.session_id,

        city=getattr(e, "city", None),
        country=getattr(e, "country", None) or "Sri Lanka",

        min_star_rating=getattr(e, "min_star_rating", None),
        max_star_rating=getattr(e, "max_star_rating", None),
        must_have_amenities=amenities,
        max_price_lkr=getattr(e, "max_price_lkr", None),

        limit=10,
        trace={
            "domain_category": getattr(parsed, "domain_category", None),
            "preference_sources": src_map,
        }
    )
