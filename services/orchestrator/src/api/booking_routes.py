from __future__ import annotations
import os
from fastapi import APIRouter, HTTPException
import httpx

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