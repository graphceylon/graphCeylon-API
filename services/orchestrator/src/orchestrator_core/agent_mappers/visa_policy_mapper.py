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
    if not s:
        return s
    x = str(s).strip()
    if x.lower().startswith("the "):
        x = x[4:].strip()

    synonyms = {
        "usa": "United States",
        "u.s.a": "United States",
        "u.s.": "United States",
        "us": "United States",
        "united states of america": "United States",
        "sri lanka": "Sri Lanka",
    }
    return synonyms.get(x.lower(), x)


def _default_ask_type() -> VisaAskType:
    for name in ("procedure", "requirements", "general", "info"):
        if hasattr(VisaAskType, name):
            return getattr(VisaAskType, name)
    return list(VisaAskType)[0]


def _infer_ask_type(raw_lower: str) -> VisaAskType:
    if any(k in raw_lower for k in ["fee", "fees", "cost", "price", "how much"]):
        return VisaAskType.fees
    if any(k in raw_lower for k in ["how long", "processing", "processing time"]):
        return VisaAskType.processing_time
    if any(k in raw_lower for k in ["extend", "extension"]):
        return VisaAskType.extension
    if any(k in raw_lower for k in ["need a visa", "do i need a visa", "eligible", "eligibility"]):
        return VisaAskType.eligibility
    return _default_ask_type()



def _infer_purpose(entities: dict, raw_lower: str) -> VisaPurpose:
    legal_service = entities.get("legal_service")
    citizenship_type = entities.get("citizenship_type")

    if legal_service == "citizenship" or citizenship_type:
        dual = getattr(VisaPurpose, "dual_citizenship", None)
        if citizenship_type == "dual_citizenship" and dual is not None:
            return dual
        return getattr(VisaPurpose, "other", VisaPurpose.tourism)

    if "business" in raw_lower:
        return getattr(VisaPurpose, "business", VisaPurpose.tourism)
    if "transit" in raw_lower:
        return getattr(VisaPurpose, "transit", VisaPurpose.tourism)
    if "study" in raw_lower or "student" in raw_lower:
        return getattr(VisaPurpose, "study", VisaPurpose.tourism)
    if "work" in raw_lower or "employment" in raw_lower:
        return getattr(VisaPurpose, "work", VisaPurpose.tourism)

    return VisaPurpose.tourism


# def map_visa_policy_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> BaseModel:
#     entities = _as_dict(getattr(parsed_intent, "entities", None))

#     raw_text = parsed_intent.raw_text or req.input_text or ""
#     raw_lower = raw_text.lower()

#     # --- travel_window ---
#     travel_start = entities.get("start_date")
#     travel_end = entities.get("end_date")
#     travel_window: Optional[TravelWindow] = None
#     if travel_start or travel_end:
#         travel_window = TravelWindow(start_date=travel_start, end_date=travel_end)

#     # ✅ ask_type ALWAYS set (no more None)
#     ask_type = _infer_ask_type(raw_lower)

#     # --- countries ---
#     nationality = entities.get("nationality_country") or entities.get("origin")
#     destination = entities.get("destination") or entities.get("country") or "Sri Lanka"

#     nationality = _normalize_country_name(nationality)
#     destination = _normalize_country_name(destination)

#     # --- purpose ---
#     purpose = _infer_purpose(entities, raw_lower)

#     # If missing nationality, return contract + missing_fields
#     if not nationality:
#         return VisaPolicyRequest(
#             intent=parsed_intent.intent or "info_visa_policy",  # ✅ explicit
#             ask_type=ask_type,                                  # ✅ always present
#             user_id=req.user_id,
#             session_id=req.session_id,
#             raw_text=raw_text,
#             nationality_country="",
#             destination_country=str(destination),
#             intended_stay_days=entities.get("days"),
#             travel_window=travel_window,
#             purpose=purpose,
#             extra={
#                 "domain_category": parsed_intent.domain_category,
#                 "confidence": parsed_intent.confidence,
#                 "missing_fields": ["nationality_country"],
#             },
#         )

#     return VisaPolicyRequest(
#         intent=parsed_intent.intent or "info_visa_policy",      # ✅ explicit
#         ask_type=ask_type,                                      # ✅ always present
#         user_id=req.user_id,
#         session_id=req.session_id,
#         raw_text=raw_text,
#         nationality_country=nationality,
#         destination_country=destination,
#         intended_stay_days=entities.get("days"),
#         travel_window=travel_window,
#         purpose=purpose,
#         extra={
#             "domain_category": parsed_intent.domain_category,
#             "confidence": parsed_intent.confidence,
#         },
#     )

def map_visa_policy_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> BaseModel:
    entities = _as_dict(getattr(parsed_intent, "entities", None))

    raw_text = parsed_intent.raw_text or req.input_text or ""
    raw_lower = raw_text.lower()

    # ✅ ask_type ALWAYS set
    ask_type = _infer_ask_type(raw_lower)

    # --- countries ---
    nationality = entities.get("nationality_country") or entities.get("origin")
    destination = entities.get("destination") or entities.get("country") or "Sri Lanka"

    nationality = _normalize_country_name(nationality)
    destination = _normalize_country_name(destination)

    # ✅ ensure non-empty strings (KG requires fields)
    missing_fields = []
    if not nationality:
        nationality = "unknown"
        missing_fields.append("nationality_country")
    if not destination:
        destination = "Sri Lanka"
        missing_fields.append("destination_country")

    # --- purpose ---
    purpose = _infer_purpose(entities, raw_lower)

    # ✅ intended_stay_days ALWAYS set (KG requires)
    days = entities.get("days")
    try:
        intended_stay_days = int(days) if days is not None else 30
    except Exception:
        intended_stay_days = 30

    # ✅ travel_window ALWAYS set (KG requires object + string fields)
    travel_start = entities.get("start_date")
    travel_end = entities.get("end_date")

    travel_window = TravelWindow(
        start_date=str(travel_start).strip() if travel_start else "unknown",
        end_date=str(travel_end).strip() if travel_end else "unknown",
    )

    return VisaPolicyRequest(
        intent=parsed_intent.intent or "info_visa_policy",
        ask_type=ask_type,
        user_id=req.user_id or "unknown",
        session_id=req.session_id or "no_session",
        raw_text=raw_text,
        nationality_country=nationality,
        destination_country=destination,
        intended_stay_days=intended_stay_days,
        travel_window=travel_window,
        purpose=purpose,
        extra={
            "domain_category": parsed_intent.domain_category,
            "confidence": parsed_intent.confidence,
            **({"missing_fields": missing_fields} if missing_fields else {}),
        },
    )

