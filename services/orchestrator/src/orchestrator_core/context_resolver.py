# orchestrator_core/context_resolver.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Any, Dict

@dataclass
class ResolvedContext:
    trip_id: Optional[str] = None
    city: Optional[str] = None
    is_new_trip: bool = False

def resolve_context(*, parsed_intent, req, session_state, trip_repo) -> ResolvedContext:
    # entities may be dict or pydantic
    ents: Dict[str, Any] = (
        parsed_intent.entities.model_dump(exclude_none=True)
        if hasattr(parsed_intent.entities, "model_dump")
        else (parsed_intent.entities or {})
    )

    intent = (parsed_intent.intent or "").strip()
    msg_city = (ents.get("city") or "").strip() or None

    active_trip_id = None
    active_place = None
    if session_state:
        active_trip_id = session_state.slots.get("active_trip_id")
        active_place = session_state.slots.get("active_place")

    # ---------- itinerary ----------
    if intent == "plan_itinerary":
        # planning always creates a new trip
        return ResolvedContext(trip_id=None, city=msg_city or active_place, is_new_trip=True)

    if intent == "modify_itinerary":
        # 1) use active trip
        if active_trip_id:
            return ResolvedContext(trip_id=str(active_trip_id), city=msg_city or active_place, is_new_trip=False)

        # 2) if city mentioned, pick latest trip for that city
        if req.user_id and msg_city:
            latest = trip_repo.get_latest_trip_for_destination(user_id=req.user_id, destination=msg_city)
            if latest:
                return ResolvedContext(trip_id=str(latest.trip_id), city=msg_city, is_new_trip=False)

        # 3) cannot resolve which trip to modify
        return ResolvedContext(trip_id=None, city=msg_city or active_place, is_new_trip=False)

    # ---------- info intents (weather/crowd/etc) ----------
    if intent in {"forecast_weather", "crowd_forecast", "forecast_price"}:
        if msg_city:
            return ResolvedContext(trip_id=active_trip_id, city=msg_city, is_new_trip=False)
        if active_place:
            return ResolvedContext(trip_id=active_trip_id, city=active_place, is_new_trip=False)

        # fallback to trip destination
        if req.user_id and active_trip_id:
            trip = trip_repo.get_trip(trip_id=active_trip_id, user_id=req.user_id)
            if trip and trip.destination:
                return ResolvedContext(trip_id=str(active_trip_id), city=str(trip.destination), is_new_trip=False)

        return ResolvedContext(trip_id=active_trip_id, city=None, is_new_trip=False)

    # default
    return ResolvedContext(trip_id=active_trip_id, city=msg_city or active_place, is_new_trip=False)