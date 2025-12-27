from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional

from ...orchestrator_core.agent_contracts.visa_policy import (
    VisaPolicyRequest,
    VisaPolicyResponse,
    PolicyRule,
    Evidence,
)
from ...orchestrator_core.agent_mappers.visa_policy_query_spec import build_visa_policy_query_spec
from .kg.repository import JsonVisaKGRepository, VisaKGRepository


class VisaPolicyAgent:
    def __init__(self, repo: VisaKGRepository):
        self.repo = repo

    def invoke(self, req: VisaPolicyRequest) -> VisaPolicyResponse:
        spec = build_visa_policy_query_spec(req)

        # MOCK KG lookup (Neo4j later)
        record = self.repo.find_policy(spec.filters)

        if not record:
            return VisaPolicyResponse(
                status="no_result",
                destination_country=req.destination_country or "Sri Lanka",
                nationality_country=req.nationality_country,
                purpose=(req.purpose.value if req.purpose else None),
                passport_type=(req.passport_type.value if req.passport_type else None),
                entry_type=(req.entry_type.value if req.entry_type else None),
                travel_window=req.travel_window,
                intended_stay_days=req.intended_stay_days,
                summary="No matching visa policy was found in the current knowledge base for the given inputs.",
                warnings=["Try specifying purpose (tourism/business) and exact nationality/passport type."],
                rules=[],
            )

        ev = Evidence(
            source=str(record.get("source") or "Visa Policy KG (Mock)"),
            url=record.get("url"),
            node_id=record.get("node_id"),
            quote=None,
            retrieved_at=datetime.utcnow().isoformat(),
        )

        details = (
            f"Visa type: {record.get('visa_type')}. "
            f"Max stay: {record.get('max_stay_days')} days. "
            f"Extendable: {record.get('extendable')}. "
            f"Estimated fee (USD): {record.get('fee_usd')}."
        )

        rule = PolicyRule(
            rule_type="eligibility",
            title=f"{req.nationality_country} → {req.destination_country} ({record.get('purpose')})",
            details=details,
            conditions={
                "purpose": record.get("purpose"),
                "max_stay_days": record.get("max_stay_days"),
                "passport_type": (req.passport_type.value if req.passport_type else None),
            },
            evidence=[ev],
        )

        return VisaPolicyResponse(
            status="ok",
            destination_country=req.destination_country or "Sri Lanka",
            nationality_country=req.nationality_country,
            purpose=(req.purpose.value if req.purpose else None),
            passport_type=(req.passport_type.value if req.passport_type else None),
            entry_type=(req.entry_type.value if req.entry_type else None),
            travel_window=req.travel_window,
            intended_stay_days=req.intended_stay_days,
            summary="Visa policy found based on current knowledge base.",
            rules=[rule],
            warnings=[],
        )


def build_default_visa_agent() -> VisaPolicyAgent:
    json_path = Path(__file__).parent / "kg" / "visa_rules.json"
    repo = JsonVisaKGRepository(str(json_path))
    return VisaPolicyAgent(repo)
