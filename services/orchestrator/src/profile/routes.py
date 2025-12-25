from __future__ import annotations
from fastapi import APIRouter, HTTPException

from ..orchestrator_core.agent_contracts.profile import UserProfile, ProfilePatch
from .repo import get_profile, upsert_profile, patch_profile

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("/{user_id}", response_model=UserProfile)
def api_get_profile(user_id: str):
    user_id = user_id.strip()   # ✅ important
    p = get_profile(user_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p


# Onboarding: create/replace profile
@router.post("/upsert", response_model=UserProfile)
def api_upsert_profile(profile: UserProfile):
    return upsert_profile(profile)

# Settings updates: patch profile
@router.patch("/{user_id}", response_model=UserProfile)
def api_patch_profile(user_id: str, patch: ProfilePatch):
    return patch_profile(user_id, patch)
