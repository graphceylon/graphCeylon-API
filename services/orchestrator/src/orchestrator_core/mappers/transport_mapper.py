from __future__ import annotations
from typing import Any, Dict

from ...api.schemas import ParsedIntent, OrchestrateRequest
from ..contracts.transport import TransportInfoRequest
def _normalize_days_int(value: Any, default: int = 1) -> int:
    try:
        if value is None:
            return default
        return max(1, int(str(value).strip()))
    except (ValueError, TypeError):
        return default

def _as_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    if isinstance(obj, dict):
        return obj
    return dict(obj)


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _normalize_days(value: Any):
    if value is None:
        return None
    if isinstance(value, list):
        out = [str(v).strip() for v in value if str(v).strip()]
        return out or None
    if isinstance(value, str):
        v = value.strip()
        return [v] if v else None
    return [str(value).strip()]


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        v = value.strip()
        return [v] if v else []
    return [str(value).strip()]


def map_transport_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> TransportInfoRequest:
    ents = _as_dict(parsed_intent.entities)
    prefs = _as_dict(parsed_intent.preference_overrides)

    origin = _clean_str(
        ents.get("origin") or ents.get("origin_city")
    )
    destination = _clean_str(
        ents.get("destination") or ents.get("city")
    )
    city = _clean_str(
        ents.get("city") or ents.get("destination")
    )

    country = _clean_str(ents.get("country")) or "Sri Lanka"
    time_of_day = _clean_str(ents.get("time_of_day"))
    days = _normalize_days_int(ents.get("days"))
    tags = _normalize_list(ents.get("tags"))

    budget_level = _clean_str(
        prefs.get("budget_level") or ents.get("budget_level")
    )
    preferred_transport = _normalize_list(
        prefs.get("preferred_transport") or ents.get("preferred_transport")
    )

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