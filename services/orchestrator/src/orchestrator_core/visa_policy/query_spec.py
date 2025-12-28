from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..agent_contracts.visa_policy import VisaPolicyRequest


@dataclass
class VisaPolicyQuerySpec:
    """
    Last orchestrator-side normalized structure before Cypher.
    KG team converts this into (cypher, params) or KG retrieval call.
    """
    intent: str
    filters: Dict[str, Any]
    time_window: Dict[str, Optional[str]]
    raw_text: str


def build_visa_policy_query_spec(req: VisaPolicyRequest) -> VisaPolicyQuerySpec:
    travel_start = req.travel_window.start_date if req.travel_window else None
    travel_end = req.travel_window.end_date if req.travel_window else None

    filters = {
        "nationality_country": req.nationality_country,
        "destination_country": req.destination_country,
        "purpose": (req.purpose.value if req.purpose else None),
        "passport_type": (req.passport_type.value if req.passport_type else None),
        "entry_type": (req.entry_type.value if req.entry_type else None),
        "intended_stay_days": req.intended_stay_days,
        "ask_type": (req.ask_type.value if req.ask_type else None),
    }

    time_window = {
        "travel_start_date": travel_start,
        "travel_end_date": travel_end,
    }

    return VisaPolicyQuerySpec(
        intent=req.intent,
        filters=filters,
        time_window=time_window,
        raw_text=req.raw_text,
    )
