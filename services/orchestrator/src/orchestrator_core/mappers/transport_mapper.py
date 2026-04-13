# from __future__ import annotations
# from typing import Any, Dict

# from ...api.schemas import ParsedIntent, OrchestrateRequest
# from ..contracts.transport import TransportInfoRequest


# def _as_dict(obj: Any) -> Dict[str, Any]:
#     if obj is None:
#         return {}
#     if hasattr(obj, "model_dump"):
#         return obj.model_dump(exclude_none=True)
#     if isinstance(obj, dict):
#         return obj
#     return dict(obj)


# def map_transport_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> TransportInfoRequest:
#     ents = _as_dict(parsed_intent.entities)
#     prefs = _as_dict(parsed_intent.preference_overrides)

#     origin = ents.get("origin")
#     destination = ents.get("destination")
#     city = ents.get("city")
#     country = ents.get("country") or "Sri Lanka"
#     time_of_day = ents.get("time_of_day")
#     days = ents.get("days")
#     tags = ents.get("tags") or []

#     # pull useful prefs if present
#     budget_level = ents.get("budget_level") or prefs.get("budget_level")
#     preferred_transport = prefs.get("preferred_transport") or []

#     trace = {
#         "intent": parsed_intent.intent,
#         "confidence": float(parsed_intent.confidence or 0.0),
#         "domain_category": getattr(parsed_intent, "domain_category", None),
#         "preferences": prefs,
#     }

#     return TransportInfoRequest(
#         origin=origin,
#         destination=destination,
#         city=city,
#         country=country,
#         time_of_day=time_of_day,
#         days=days,
#         budget_level=budget_level,
#         preferred_transport=preferred_transport,
#         tags=tags,
#         user_id=req.user_id,
#         session_id=req.session_id,
#         query=req.input_text,
#         trace=trace,
#     )
from __future__ import annotations
from typing import Any, Dict

from ...api.schemas import ParsedIntent, OrchestrateRequest
from ..contracts.transport import TransportInfoRequest


def _as_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    if isinstance(obj, dict):
        return obj
    return dict(obj)


def map_transport_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> TransportInfoRequest:
    ents = _as_dict(parsed_intent.entities)
    prefs = _as_dict(parsed_intent.preference_overrides)

    # Use fallback chain because extractor may fill origin_city / city instead
    origin = ents.get("origin") or ents.get("origin_city")
    destination = ents.get("destination") or ents.get("city")
    city = ents.get("city") or ents.get("destination")

    country = ents.get("country") or "Sri Lanka"
    time_of_day = ents.get("time_of_day")
    days = ents.get("days")
    tags = ents.get("tags") or []

    budget_level = ents.get("budget_level") or prefs.get("budget_level")
    preferred_transport = prefs.get("preferred_transport") or []

    trace = {
        "intent": parsed_intent.intent,
        "confidence": float(parsed_intent.confidence or 0.0),
        "domain_category": getattr(parsed_intent, "domain_category", None),
        "preferences": prefs,
    }

    return TransportInfoRequest(
        origin=origin,
        destination=destination,
        city=city,
        country=country,
        time_of_day=time_of_day,
        days=days,
        budget_level=budget_level,
        preferred_transport=preferred_transport,
        tags=tags,
        user_id=req.user_id,
        session_id=req.session_id,
        query=req.input_text,
        trace=trace,
    )