from typing import Any, Dict
from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.itinerary_modify import ItineraryModifyRequest  # your pydantic contract
from .modify_ops_builder import build_modify_ops

def map_itinerary_modify_request(
    parsed_intent: ParsedIntent,
    req: OrchestrateRequest,
    trip_id: str,
    existing_plan: Dict[str, Any],
    merged_prefs: Dict[str, Any],
) -> ItineraryModifyRequest:
    entities = parsed_intent.entities.model_dump() if hasattr(parsed_intent.entities, "model_dump") else dict(parsed_intent.entities or {})
    overrides = parsed_intent.preference_overrides or {}

    ops = build_modify_ops(
        parsed_entities=entities,
        preference_overrides=overrides,
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