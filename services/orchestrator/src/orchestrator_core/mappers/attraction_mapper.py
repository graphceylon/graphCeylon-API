from __future__ import annotations
from typing import Any, Dict

from ...api.schemas import ParsedIntent, OrchestrateRequest
from ..contracts.attraction import AttractionInfoRequest


def _as_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    if isinstance(obj, dict):
        return obj
    return dict(obj)


def map_attraction_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> AttractionInfoRequest:
    ents = _as_dict(parsed_intent.entities)
    prefs = _as_dict(parsed_intent.preference_overrides)

    # basic entity fields
    city = ents.get("city")
    country = ents.get("country") or "Sri Lanka"
    poi_name = ents.get("poi_name")
    poi_category = ents.get("poi_category")
    days = ents.get("days")
    tags = ents.get("tags") or []

    # lightweight trace you can enrich later
    trace = {
        "intent": parsed_intent.intent,
        "confidence": float(parsed_intent.confidence or 0.0),
        "domain_category": getattr(parsed_intent, "domain_category", None),
        "preferences": prefs,
    }

    return AttractionInfoRequest(
        city=city,
        country=country,
        poi_name=poi_name,
        poi_category=poi_category,
        days=days,
        tags=tags,
        user_id=req.user_id,
        session_id=req.session_id,
        query=req.input_text,
        trace=trace,
    )
