# services/orchestrator/src/orchestrator_core/routing/session_enricher.py
from __future__ import annotations
from typing import Any, Dict, Optional


def enrich_entities_from_session(
    ents: Dict[str, Any],
    session_slots: Optional[Dict[str, Any]],
    resolved: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Only fill missing fields. Never overwrite user-provided entities.
    """
    out = dict(ents or {})
    slots = session_slots or {}

    def pick(*vals):
        for v in vals:
            if v is not None and str(v).strip() != "":
                return v
        return None

    if not out.get("city"):
        out["city"] = pick(
            getattr(resolved, "city", None) if resolved else None,
            slots.get("city"),
            slots.get("active_place"),
        )

    if not out.get("country"):
        out["country"] = pick(
            getattr(resolved, "country", None) if resolved else None,
            slots.get("country"),
        )

    return out