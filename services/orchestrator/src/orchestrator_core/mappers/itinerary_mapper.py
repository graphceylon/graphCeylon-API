# # services/orchestrator/src/orchestrator_core/mappers/itinerary_mapper.py

# from __future__ import annotations

# from typing import Any, Dict, Optional

# from ...api.schemas import OrchestrateRequest, ParsedIntent
# from ..contracts.itinerary import ItineraryPlanRequest


# def _canon_budget(v: Any) -> str:
#     """
#     Your ItineraryPlanRequest expects: low|mid|high|unknown
#     Normalize common variants.
#     """
#     if not isinstance(v, str):
#         return "unknown"
#     x = v.strip().lower()
#     if x in {"medium", "mid"}:
#         return "mid"
#     if x in {"low", "high", "unknown"}:
#         return x
#     return "unknown"


# def _merge_prefs(profile: Optional[Dict[str, Any]], instant: Optional[Dict[str, Any]]) -> Dict[str, Any]:
#     """
#     Instant (query overrides) wins if it has a meaningful value.
#     Lists: use instant list if non-empty else profile list.
#     Scalars: use instant if not None else profile.
#     """
#     out: Dict[str, Any] = dict(profile or {})
#     for k, v in (instant or {}).items():
#         if v is None:
#             continue
#         if isinstance(v, list):
#             if len(v) > 0:
#                 out[k] = v
#         else:
#             out[k] = v
#     return out


# def map_itinerary_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> ItineraryPlanRequest:
#     e = parsed_intent.entities
#     p = parsed_intent.preference_overrides  # <-- already merged by orchestrator

#     destination = e.city or e.destination or e.country

#     return ItineraryPlanRequest(
#         intent="plan_itinerary",
#         user_id=req.user_id,
#         session_id=req.session_id,
#         raw_text=req.input_text,

#         city=e.city,
#         country=e.country,
#         time_of_day=e.time_of_day,

#         # trip core
#         days=e.days,
#         destination=destination,
#         start_date=e.start_date,
#         end_date=e.end_date,

#         # preferences (merged; query wins)
#         travel_style=(p.get("travel_style") or []),
#         eco_preference=p.get("eco_preference"),
#         avoid_crowds=p.get("avoid_crowds"),
#         food_preferences=(p.get("food_preferences") or []),
#         budget_level=(p.get("budget_level") or "unknown"),

#         # constraints (trip-only)
#         max_trip_budget_lkr=e.max_price_lkr,
#         currency=(e.currency or "LKR"),

#         # passthrough tags/debug
#         tags=(e.tags or []),
#     )
from __future__ import annotations
from typing import Any, Dict
from datetime import date, timedelta

from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.c3_common import C3RequestEnvelope
from ..geo.region_resolver import resolve_region_scope


def map_itinerary_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> C3RequestEnvelope:
    e = parsed_intent.entities
    p = parsed_intent.preference_overrides or {}

    destination = e.city or e.destination or e.country
    scope = resolve_region_scope(
        city=e.city,
        region=getattr(e, "region", None),
        country=e.country,
    )


    # ✅ Guarantee start_date for C3 (because C3 requires it)
    start_date = e.start_date or str(date.today())
    days = int(e.days or 3)
    end_date = e.end_date or str(date.fromisoformat(start_date) + timedelta(days=days - 1))

    query: Dict[str, Any] = {
        "raw_text": req.input_text,
        "city": e.city,
        "destination": destination,
        "region": getattr(e, "region", None),
        "country": e.country or "Sri Lanka",
        "days": days,
        "origin_city": getattr(e, "origin", None) or getattr(e, "origin_city", None),

        "start_date": start_date,
        "end_date": end_date,
        "tags": e.tags or [],
        "time_of_day": getattr(e, "time_of_day", None),
        "geo_scope": {
            "mode": scope.mode,              # "city" | "region" | "country"
            "region_key": scope.region_key,  # normalized string
            "districts": scope.districts,    # list[str] or None
            "debug": scope.debug,
        },
    }

    prefs: Dict[str, Any] = {
        # key ones you already use
        "travel_style": p.get("travel_style") or [],
        "food_preferences": p.get("food_preferences") or [],
        "eco_preference": p.get("eco_preference"),
        "avoid_crowds": p.get("avoid_crowds"),
        "budget_level": p.get("budget_level"),
        "budget_per_night_lkr": p.get("budget_per_night_lkr"),
        "temperature_preference": p.get("temperature_preference"),
        "rain_preference": p.get("rain_preference"),
        "activity_preference": p.get("activity_preference"),
        "preferred_transport": p.get("preferred_transport") or [],
        "pace_preference": p.get("pace_preference"),
        "adventure_level": p.get("adventure_level"),
        "walking_tolerance_minutes": p.get("walking_tolerance_minutes"),
        "must_have_amenities": p.get("must_have_amenities") or [],
        "accommodation_type": p.get("accommodation_type"),
        "star_preference": p.get("star_preference"),
        "cancellation_preference": p.get("cancellation_preference"),
    }

    constraints: Dict[str, Any] = {
        "max_trip_budget_lkr": getattr(e, "max_price_lkr", None),
        "currency": getattr(e, "currency", None) or "LKR",
        # optional planner knobs
        "max_candidates": 80,
        "per_day_attractions": 2,
        "meals_per_day": 1,
    }

    # trace will be filled in orchestrator_service (preference_sources + semantic recall)
    return C3RequestEnvelope(
        intent="plan_itinerary",
        user_id=req.user_id,
        session_id=req.session_id,
        query=query,
        prefs=prefs,
        constraints=constraints,
        trace={},
    )
