from __future__ import annotations
import os
from fastapi import APIRouter, HTTPException
import httpx
from fastapi import APIRouter, Depends, HTTPException

from uuid import UUID
from .booking_schemas import (
    BookingDraftCreate,
    BookingDraftResponse,
    BookingHITLRequest,
    BookingHITLApprove,
    BookingConfirmRequest,
)
from .booking_repo import BookingDraftRepo

router = APIRouter(prefix="/booking", tags=["booking"])
PMS_BASE = os.getenv("HOTEL_API_BASE", "http://190.92.219.12:8087")

DB_DSN = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL") or os.getenv("PROFILE_EVENTS_DB_DSN")
if not DB_DSN:
    # Keep explicit; you want a clear crash in dev if DSN not set.
    raise RuntimeError("POSTGRES_DSN/DATABASE_URL not set for booking lifecycle.")

repo = BookingDraftRepo(DB_DSN)
@router.post("/confirm", response_model=BookingDraftResponse)
def confirm_booking(req: BookingConfirmRequest):
    st = repo.get_status(req.draft_id)
    if not st:
        raise HTTPException(404, "Draft not found.")
    if st != "APPROVED":
        raise HTTPException(409, f"Cannot confirm from status={st}.")

    draft = repo.get_draft(req.draft_id)  # <-- implement this (fetch JSON)
    if not draft:
        raise HTTPException(404, "Draft not found.")

    payload = {
        "CountryCode": draft.get("country_code") or "LKA",
        "Arrival": draft["arrival"],
        "Departure": draft["departure"],
        "PropertyCode": draft["property_code"],  # "ABR"
        "Uuid": str(req.draft_id),
        "Remarks": draft.get("remarks") or "Reservation created by Graph Ceylon (HITL approved)",
        "Rooms": draft["rooms"],  # list of dicts with RoomCategoryId, RateCodeHeaderId, etc.
    }

    try:
        with httpx.Client(timeout=25.0) as client:
            # if you need auth headers, add them here
            r = client.post(f"{PMS_BASE}/api/external/createreservationforai", json=payload)
            r.raise_for_status()
            pms_resp = r.json()
    except Exception as e:
        repo.set_status(req.draft_id, "FAILED", failure_reason=str(e))
        raise HTTPException(502, f"PMS reservation failed: {e}")

    if str(pms_resp.get("HttpCode")) != "200":
        repo.set_status(req.draft_id, "FAILED", failure_reason=pms_resp.get("Description"))
        raise HTTPException(502, f"PMS rejected: {pms_resp.get('Description')}")

    # store whatever reference PMS returns (depends on response shape)
    confirmed_ref = pms_resp.get("Data") or "CONFIRMED"
    repo.set_status(req.draft_id, "CONFIRMED", confirmed_ref=str(confirmed_ref))

    return BookingDraftResponse(
        draft_id=req.draft_id,
        status="CONFIRMED",
        message=f"Confirmed via PMS (ref {confirmed_ref}).",
    )
@router.patch("/draft/{draft_id}", response_model=BookingDraftResponse)
def update_draft(draft_id: UUID, req: BookingDraftCreate):
    st = repo.get_status(draft_id)
    if not st:
        raise HTTPException(404, "Draft not found.")
    if st not in ("DRAFT", "REJECTED"):
        raise HTTPException(409, f"Cannot update draft in status={st}.")
    repo.update_draft(draft_id, req.model_dump())
    return BookingDraftResponse(
        draft_id=draft_id,
        status="DRAFT",
        message="Draft updated.",
    )
@router.post("/draft", response_model=BookingDraftResponse)
def create_draft(req: BookingDraftCreate):
    draft_id = repo.create_draft(req.model_dump())
    return BookingDraftResponse(draft_id=draft_id, status="DRAFT", message="Draft created.")


@router.post("/hitl/request", response_model=BookingDraftResponse)
def request_hitl(req: BookingHITLRequest):
    st = repo.get_status(req.draft_id)
    if not st:
        raise HTTPException(404, "Draft not found.")
    if st not in ("DRAFT", "REJECTED"):
        raise HTTPException(409, f"Cannot request approval from status={st}.")
    repo.set_status(req.draft_id, "PENDING_APPROVAL")
    return BookingDraftResponse(draft_id=req.draft_id, status="PENDING_APPROVAL", message="Sent for approval.")


@router.post("/hitl/approve", response_model=BookingDraftResponse)
def approve_hitl(req: BookingHITLApprove):
    st = repo.get_status(req.draft_id)
    if not st:
        raise HTTPException(404, "Draft not found.")
    if st != "PENDING_APPROVAL":
        raise HTTPException(409, f"Cannot approve from status={st}.")

    if req.approve:
        repo.set_status(
            req.draft_id,
            "APPROVED",
            approved_by=req.admin_id or "admin",
            approval_reason=req.reason,
        )
        return BookingDraftResponse(draft_id=req.draft_id, status="APPROVED", message="Approved.")
    else:
        repo.set_status(
            req.draft_id,
            "REJECTED",
            approved_by=req.admin_id or "admin",
            rejected_reason=req.reason or "Rejected by admin.",
        )
        return BookingDraftResponse(draft_id=req.draft_id, status="REJECTED", message="Rejected.")


# @router.post("/confirm", response_model=BookingDraftResponse)
# def confirm_booking(req: BookingConfirmRequest):
#     st = repo.get_status(req.draft_id)
#     if not st:
#         raise HTTPException(404, "Draft not found.")
#     if st != "APPROVED":
#         raise HTTPException(409, f"Cannot confirm from status={st}.")

#     # TODO: call PMS "create booking" endpoint here when you have it.
#     # Demo-safe fallback:
#     fake_ref = f"INQ-{str(req.draft_id)[:8].upper()}"
#     repo.set_status(req.draft_id, "CONFIRMED", confirmed_ref=fake_ref)

#     return BookingDraftResponse(draft_id=req.draft_id, status="CONFIRMED", message=f"Confirmed (ref {fake_ref}).")

# booking_router.py — add this endpoint

@router.post("/request/{draft_id}")
def submit_booking_request(draft_id: str):
    # 1) fetch raw_payload using existing repo method
    raw = repo.fetch_draft_payload(draft_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft_data = raw.get("draft") or {}
    hotel_data = raw.get("hotel") or {}
    search_data = raw.get("search") or {}
    rooms_list = draft_data.get("rooms") or []

    # 2) build createreservationforai payload
    reservation_payload = {
        "CountryCode": draft_data.get("country_code") or "LKA",
        "Arrival": draft_data.get("arrival") or search_data.get("arrival"),
        "Departure": draft_data.get("departure") or search_data.get("departure"),
        "PropertyCode": hotel_data.get("property_code") or draft_data.get("property_code"),
        "Uuid": f"gc-{str(draft_id)[:8]}",
        "Remarks": "Booking request via GraphCeylon AI",
        "Rooms": rooms_list or [
            {
                "RoomCategoryId": raw.get("selected", {}).get("room_category_id"),
                "RateCodeHeaderId": raw.get("selected", {}).get("rate_code_id"),
                "RoomTypeId": raw.get("selected", {}).get("room_type_id"),
                "MealPlanId": raw.get("selected", {}).get("meal_plan_id"),
                "NoOfRooms": 1,
            }
        ],
    }

    print(f"[booking/request] draft_id={draft_id}")
    print(f"[booking/request] reservation_payload={reservation_payload}")

    # 3) call hotel API
    base_url = os.getenv("HOTEL_EXTERNAL_BASE_URL", "http://190.92.219.12:8087")
    try:
        with httpx.Client(timeout=30.0) as client:
            token_resp = client.post(
                f"{base_url}/token",
                data={
                    "grant_type": os.getenv("HOTEL_OAUTH_GRANT_TYPE", "password"),
                    "username": os.getenv("HOTEL_OAUTH_USERNAME", "externalAPI"),
                    "password": os.getenv("HOTEL_OAUTH_PASSWORD", "e@x$&n!l&12E"),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_resp.raise_for_status()
            token = token_resp.json().get("access_token")
            if not token:
                raise HTTPException(status_code=502, detail="Failed to get hotel API token")

            res = client.post(
                f"{base_url}/api/external/createreservationforai",
                json=reservation_payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
            print(f"[booking/request] hotel status={res.status_code} body={res.text[:1000]}")
            if res.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Hotel API returned {res.status_code}: {res.text[:500]}")
            hotel_response = res.json()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Hotel API error: {e}")

    print(f"[booking/request] hotel_response={hotel_response}")

    reservation_data = hotel_response.get("Data") or {}
    reservation_no = reservation_data.get("ReservationNo") or f"gc-{str(draft_id)[:8].upper()}"
    group_no = reservation_data.get("GroupReservationNo")
    confirmation_url = reservation_data.get("ConfirmationUrl")

    # hotel API returned success even without ReservationNo — use our uuid as ref
    print(f"[booking/request] reservation_no={reservation_no} confirmation_url={confirmation_url}")

    if not reservation_no:
        raise HTTPException(status_code=502, detail=f"Hotel API did not return a ReservationNo. Response: {hotel_response}")

    # 4) update status using existing repo
    repo.set_status(draft_id, "PENDING_APPROVAL", confirmed_ref=reservation_no)

    return {
        "ok": True,
        "draft_id": str(draft_id),
        "reservation_no": reservation_no,
        "group_reservation_no": group_no,
        "confirmation_url": confirmation_url,
        "message": f"Your booking request has been submitted! Reference: {reservation_no}",
    }