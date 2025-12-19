from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from ...api.schemas import ParsedIntent, OrchestrateRequest
from ..agent_contracts.visa_policy import (
    VisaPolicyRequest,
    TravelWindow,
    VisaPurpose,
    VisaAskType,
)


def _as_dict(obj: Any) -> dict:
    """
    Convert Pydantic models / dicts into a plain dict safely.
    """
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    # Pydantic v2
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    # Pydantic v1 fallback
    if hasattr(obj, "dict"):
        return obj.dict()
    return {}


def map_visa_policy_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> BaseModel:
    """
    Convert ParsedIntent + OrchestrateRequest into the canonical VisaPolicyRequest
    that the VisaPolicyAgent / KG interface layer will accept.
    """

    entities = _as_dict(getattr(parsed_intent, "entities", None))

    nationality = entities.get("nationality_country") or entities.get("origin")
    destination = entities.get("destination") or entities.get("country") or "Sri Lanka"

    if not nationality:
        raise ValueError("Missing nationality_country for visa query")

    travel_start = entities.get("start_date")
    travel_end = entities.get("end_date")

    travel_window: Optional[TravelWindow] = None
    if travel_start or travel_end:
        travel_window = TravelWindow(start_date=travel_start, end_date=travel_end)

    # Optional: infer ask_type a bit from raw text (can stay None too)
    raw = (parsed_intent.raw_text or "").lower()
    ask_type: Optional[VisaAskType] = None
    if "fee" in raw or "cost" in raw or "price" in raw:
        ask_type = VisaAskType.fees
    elif "how long" in raw or "processing" in raw:
        ask_type = VisaAskType.processing_time
    elif "extend" in raw or "extension" in raw:
        ask_type = VisaAskType.extension
    elif "need a visa" in raw or "do i need a visa" in raw or "eligib" in raw:
        ask_type = VisaAskType.eligibility

    return VisaPolicyRequest(
        user_id=req.user_id,
        session_id=req.session_id,
        raw_text=parsed_intent.raw_text or req.input_text or "",
        nationality_country=str(nationality),
        destination_country=str(destination),
        intended_stay_days=entities.get("days"),
        travel_window=travel_window,
        purpose=VisaPurpose.tourism,
        ask_type=ask_type,
        extra={
            "domain_category": parsed_intent.domain_category,
            "confidence": parsed_intent.confidence,
        },
    )
