from typing import Any, Dict
from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.itinerary_modify import ItineraryModifyRequest
from .modify_ops_builder import build_modify_ops

def map_itinerary_modify_request(
    parsed_intent: ParsedIntent,
    req: OrchestrateRequest,
) -> ItineraryModifyRequest:

    entities: Dict[str, Any] = (
        parsed_intent.entities.model_dump(exclude_none=True)
        if hasattr(parsed_intent.entities, "model_dump")
        else dict(parsed_intent.entities or {})
    )

    # ✅ MUST exist (or modify can't work)
    trip_id = entities.get("itinerary_id") or entities.get("trip_id")
    existing_plan = entities.get("current_itinerary") or {}

    # ✅ merged prefs are already placed into preference_overrides by your orchestrator
    merged_prefs = (
        parsed_intent.preference_overrides.model_dump(exclude_none=True)
        if hasattr(parsed_intent.preference_overrides, "model_dump")
        else dict(parsed_intent.preference_overrides or {})
    )

    ops = build_modify_ops(
        parsed_entities=entities,
        preference_overrides=merged_prefs,
        raw_text=req.input_text,
        existing_plan=existing_plan,
    )

    return ItineraryModifyRequest(
        trip_id=trip_id,
        existing_plan=existing_plan,
        change_request={
            "ops": ops,
            "notes": req.input_text,
            "strict": False,
        },
        context={
            "user_id": req.user_id,
            "session_id": req.session_id,
            "lang": req.lang,
            "channel": req.channel,
            "prefs": merged_prefs,
        },
    )