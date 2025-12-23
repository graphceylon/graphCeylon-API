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
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):  # Pydantic v2
        return obj.model_dump()
    if hasattr(obj, "dict"):  # Pydantic v1
        return obj.dict()
    return {}


def _normalize_country_name(s: Optional[str]) -> Optional[str]:
    """
    Quick normalization so KG matching doesn't break on 'the United States' etc.
    Keep it simple; you can expand later.
    """
    if not s:
        return s
    x = str(s).strip()

    # remove leading "the "
    if x.lower().startswith("the "):
        x = x[4:].strip()

    # common synonyms
    synonyms = {
        "usa": "United States",
        "u.s.a": "United States",
        "u.s.": "United States",
        "us": "United States",
        "united states of america": "United States",
        "sri lanka": "Sri Lanka",
    }
    key = x.lower()
    return synonyms.get(key, x)


def _infer_purpose(raw: str) -> VisaPurpose:
    """
    Your contract currently only has VisaPurpose enum.
    When the user asks about citizenship/dual citizenship, map it to 'other' for now.
    (Later you can introduce CitizenshipPurpose / separate intent.)
    """
    r = raw.lower()

    citizenship_terms = [
        "citizenship",
        "dual citizenship",
        "dual-citizenship",
        "register citizenship",
        "citizenship fee",
        "citizenship fees",
    ]
    if any(t in r for t in citizenship_terms):
        return VisaPurpose.other

    # visa purposes
    if "business" in r:
        return VisaPurpose.business
    if "transit" in r:
        return VisaPurpose.transit
    if "study" in r or "student" in r:
        return VisaPurpose.study
    if "work" in r or "employment" in r:
        return VisaPurpose.work

    return VisaPurpose.tourism


def map_visa_policy_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> BaseModel:
    entities = _as_dict(getattr(parsed_intent, "entities", None))

    raw_text = parsed_intent.raw_text or req.input_text or ""
    raw = raw_text.lower()

    nationality = entities.get("nationality_country") or entities.get("origin")
    destination = entities.get("destination") or entities.get("country") or "Sri Lanka"

    nationality = _normalize_country_name(nationality)
    destination = _normalize_country_name(destination)

    if not nationality:
        raise ValueError("Missing nationality_country for visa query")

    travel_start = entities.get("start_date")
    travel_end = entities.get("end_date")

    travel_window: Optional[TravelWindow] = None
    if travel_start or travel_end:
        travel_window = TravelWindow(start_date=travel_start, end_date=travel_end)

    # infer ask_type from raw text
    ask_type: Optional[VisaAskType] = None
    if any(k in raw for k in ["fee", "fees", "cost", "price", "how much"]):
        ask_type = VisaAskType.fees
    elif any(k in raw for k in ["how long", "processing", "processing time"]):
        ask_type = VisaAskType.processing_time
    elif any(k in raw for k in ["extend", "extension"]):
        ask_type = VisaAskType.extension
    elif any(k in raw for k in ["need a visa", "do i need a visa", "eligible", "eligibility"]):
        ask_type = VisaAskType.eligibility

    legal_service = entities.get("legal_service")
    cit_type = entities.get("citizenship_type")

    purpose = VisaPurpose.tourism
    if legal_service == "citizenship" or cit_type == "dual_citizenship":
        purpose = VisaPurpose.dual_citizenship  # you already have this enum now


    return VisaPolicyRequest(
        user_id=req.user_id,
        session_id=req.session_id,
        raw_text=raw_text,
        nationality_country=nationality,
        destination_country=destination,
        intended_stay_days=entities.get("days"),
        travel_window=travel_window,
        purpose=purpose,          # ✅ FIX: not hard-coded
        ask_type=ask_type,
        extra={
            "domain_category": parsed_intent.domain_category,
            "confidence": parsed_intent.confidence,
        },
    )
