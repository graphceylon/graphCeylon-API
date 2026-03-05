from __future__ import annotations
import os
import httpx
from typing import Any, Dict, Optional
from uuid import UUID

BOOKING_SERVICE_URL = os.getenv(
    "BOOKING_SERVICE_URL", "http://127.0.0.1:8002"
).rstrip("/")


def _build_draft_payload(
    user_id: str,
    session_id: str,
    booking_result: Dict[str, Any],
) -> Dict[str, Any]:
    hotel = booking_result.get("hotel") or {}
    draft = booking_result.get("draft") or {}
    selected = booking_result.get("selected") or {}
    pricing = draft.get("pricing") or {}
    search = booking_result.get("search") or {}
    breakdown = pricing.get("breakdown") or []

    price_breakdown = [
        {"date": b.get("date"), "rate_lkr": b.get("rate_lkr")}
        for b in breakdown
    ]

    return {
        "user_id": str(user_id),
        "session_id": session_id,
        "city": draft.get("city") or hotel.get("city"),
        "arrival": draft.get("arrival"),
        "departure": draft.get("departure"),
        "adults": int(search.get("adults") or draft.get("adults") or 2),
        "property_id": int(hotel.get("property_id")) if hotel.get("property_id") else None,
        "property_code": hotel.get("property_code"),
        "property_name": hotel.get("name"),
        "room_category_id": int(selected.get("room_category_id")),
        "room_type_id": int(selected.get("room_type_id")),
        "meal_plan_id": int(selected.get("meal_plan_id")),
        "rate_code_id": int(selected.get("rate_code_id")) if selected.get("rate_code_id") else None,
        "currency_code": pricing.get("currency") or "LKR",
        "adult_rate": float(pricing.get("total_lkr") or 0.0),
        "price_breakdown": price_breakdown,
        "raw_payload": booking_result,
    }


def save_booking_draft(
    *,
    user_id: str,
    session_id: str,
    booking_result: Dict[str, Any],
    existing_draft_id: Optional[str] = None,  # ✅ if set → UPDATE, else CREATE
) -> Optional[str]:
    """
    Creates or updates a booking draft.
    Returns draft_id string, or None on failure.
    Never raises — booking persistence should not crash orchestration.
    """
    try:
        payload = _build_draft_payload(user_id, session_id, booking_result)

        with httpx.Client(timeout=10.0) as client:

            # ── UPDATE existing draft ──
            if existing_draft_id:
                resp = client.patch(
                    f"{BOOKING_SERVICE_URL}/booking/draft/{existing_draft_id}",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                print(f"[booking] draft updated: draft_id={existing_draft_id}")
                return existing_draft_id

            # ── CREATE new draft ──
            resp = client.post(
                f"{BOOKING_SERVICE_URL}/booking/draft",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            draft_id = str(data.get("draft_id") or "")
            print(f"[booking] draft created: draft_id={draft_id}")
            return draft_id if draft_id else None

    except Exception as e:
        print(f"[booking] WARNING: failed to save draft: {e}")
        return None