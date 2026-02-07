from typing import Any, Dict, Optional
from .travel_mode import TravelMode

def needs_clarification(payload: Dict[str, Any], tm: TravelMode) -> Optional[Dict[str, Any]]:
    days = int(payload.get("days") or 1)

    # if corridor intended but origin is missing and days >= 2 → ask one smart question
    wants_corridor = (tm.type == "corridor" and tm.include_stops)

    # origin missing means origin_confidence unknown and origin_city is None
    origin_missing = (tm.origin_confidence == "unknown") and (not tm.origin_city)

    if origin_missing and wants_corridor and days >= 2:
        return {
            "status": "needs_clarification",
            "reason": "origin_required_for_corridor",
            "question": (
                f"Are you starting from Colombo or already in {tm.destination_city}? "
                "If from Colombo, would you like to visit places on the way?"
            ),
            "options": ["Starting from Colombo + stops", f"Already in {tm.destination_city}", "Other"],
        }

    # if days == 1 → never block
    return None
