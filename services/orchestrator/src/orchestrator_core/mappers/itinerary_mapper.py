# services/orchestrator/src/orchestrator_core/mappers/itinerary_mapper.py

from __future__ import annotations

from typing import Any, Dict, Optional

from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.itinerary import ItineraryPlanRequest


def _canon_budget(v: Any) -> str:
    """
    Your ItineraryPlanRequest expects: low|mid|high|unknown
    Normalize common variants.
    """
    if not isinstance(v, str):
        return "unknown"
    x = v.strip().lower()
    if x in {"medium", "mid"}:
        return "mid"
    if x in {"low", "high", "unknown"}:
        return x
    return "unknown"


def _merge_prefs(profile: Optional[Dict[str, Any]], instant: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Instant (query overrides) wins if it has a meaningful value.
    Lists: use instant list if non-empty else profile list.
    Scalars: use instant if not None else profile.
    """
    out: Dict[str, Any] = dict(profile or {})
    for k, v in (instant or {}).items():
        if v is None:
            continue
        if isinstance(v, list):
            if len(v) > 0:
                out[k] = v
        else:
            out[k] = v
    return out


def map_itinerary_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> ItineraryPlanRequest:
    e = parsed_intent.entities
    p = parsed_intent.preference_overrides  # <-- already merged by orchestrator

    destination = e.city or e.destination or e.country

    return ItineraryPlanRequest(
        intent="plan_itinerary",
        user_id=req.user_id,
        session_id=req.session_id,
        raw_text=req.input_text,

        city=e.city,
        country=e.country,
        time_of_day=e.time_of_day,

        # trip core
        days=e.days,
        destination=destination,
        start_date=e.start_date,
        end_date=e.end_date,

        # preferences (merged; query wins)
        travel_style=(p.get("travel_style") or []),
        eco_preference=p.get("eco_preference"),
        avoid_crowds=p.get("avoid_crowds"),
        food_preferences=(p.get("food_preferences") or []),
        budget_level=(p.get("budget_level") or "unknown"),

        # constraints (trip-only)
        max_trip_budget_lkr=e.max_price_lkr,
        currency=(e.currency or "LKR"),

        # passthrough tags/debug
        tags=(e.tags or []),
    )