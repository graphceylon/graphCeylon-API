from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .db import SessionLocal
from .models import UserProfileRow

from ..orchestrator_core.agent_contracts.profile import UserProfile, ProfilePatch
import json
from pydantic_core import to_jsonable_python



def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_server_fields(data: Dict[str, Any], user_id: str, row: UserProfileRow | None) -> Dict[str, Any]:
    """
    Enforce server-owned fields and keep DB PK consistent with payload.
    """
    data = dict(data or {})

    # Ensure identity block exists
    ident = data.get("identity") or {}
    ident["user_id"] = user_id
    data["identity"] = ident

    # Server-owned fields
    if row is not None:
        data["profile_version"] = row.profile_version
        data["updated_at_iso"] = (row.updated_at.isoformat() if row.updated_at else None)

    return data


def get_profile(user_id: str) -> UserProfile | None:
    db = SessionLocal()
    try:
        row = db.get(UserProfileRow, user_id)
        if row is None:
            return None
        data = _ensure_server_fields(row.profile or {}, user_id=user_id, row=row)
        return UserProfile.model_validate(data)
    finally:
        db.close()


def upsert_profile(profile: UserProfile) -> UserProfile:
    """
    Upsert a full profile document.
    Uses DB PK = profile.identity.user_id.
    """
    db = SessionLocal()
    try:
        user_id = profile.identity.user_id

        row = db.get(UserProfileRow, user_id)
        if row is None:
            row = UserProfileRow(user_id=user_id)
            db.add(row)

        payload = to_jsonable_python(profile.model_dump())


        # Always enforce PK + server timestamps
        payload.setdefault("identity", {})
        payload["identity"]["user_id"] = user_id
        payload["updated_at_iso"] = _utc_iso()

        # Version: if caller didn't set it, keep existing or default to 1
        existing_version = int(row.profile_version or 1)
        requested_version = payload.get("profile_version")
        payload["profile_version"] = int(requested_version) if requested_version else existing_version
        # extra safety (ensures no non-JSON types sneak in)
        payload = json.loads(json.dumps(payload, default=str))


        row.profile = payload
        row.profile_version = int(payload["profile_version"])

        db.commit()
        db.refresh(row)

        out = _ensure_server_fields(row.profile or {}, user_id=user_id, row=row)
        return UserProfile.model_validate(out)
    finally:
        db.close()


def patch_profile(user_id: str, patch: ProfilePatch) -> UserProfile:
    """
    Patch parts of a profile (preferred for settings / onboarding updates).
    Bumps profile_version by +1 on each patch.
    """
    db = SessionLocal()
    try:
        row = db.get(UserProfileRow, user_id)

        if row is None:
            # create minimal profile if missing
            base = UserProfile(identity={"user_id": user_id})
            row = UserProfileRow(
                user_id=user_id,
                profile=base.model_dump(),
                profile_version=1,
            )
            db.add(row)
            db.commit()
            db.refresh(row)

        current: Dict[str, Any] = dict(row.profile or {})
        current = _ensure_server_fields(current, user_id=user_id, row=row)

        # ---------- identity updates ----------
        if patch.username is not None:
            current.setdefault("identity", {}).update({"username": patch.username})
        if patch.full_name is not None:
            current.setdefault("identity", {}).update({"full_name": patch.full_name})

        # ---------- demographics updates ----------
        if patch.country is not None or patch.date_of_birth is not None:
            demo = current.get("demographics") or {}
            if patch.country is not None:
                demo["country"] = patch.country
            if patch.date_of_birth is not None:
                demo["date_of_birth"] = patch.date_of_birth
            current["demographics"] = demo

        # ---------- languages updates ----------
        if patch.primary_language is not None or patch.secondary_languages is not None:
            langs = current.get("languages") or {}
            if patch.primary_language is not None:
                langs["primary_language"] = patch.primary_language
            if patch.secondary_languages is not None:
                langs["secondary_languages"] = patch.secondary_languages
            current["languages"] = langs

        # ---------- travel defaults ----------
        if patch.home_city is not None:
            current["home_city"] = patch.home_city
        if patch.default_party is not None:
            current["default_party"] = patch.default_party
        if patch.budget_level is not None:
            current["budget_level"] = patch.budget_level

        # ---------- preference_overrides (merge) ----------
        if patch.preference_overrides is not None:
            cur = current.get("preference_overrides") or {}
            incoming = patch.preference_overrides.model_dump(exclude_unset=True)
            cur.update(incoming)
            current["preference_overrides"] = cur

        # ---------- onboarding (merge) ----------
        if patch.onboarding is not None:
            cur_onb = current.get("onboarding") or {}
            incoming = patch.onboarding.model_dump(exclude_unset=True)
            cur_onb.update(incoming)
            current["onboarding"] = cur_onb

        # bump version + timestamps
        current_version = int(current.get("profile_version") or row.profile_version or 1)
        current["profile_version"] = current_version + 1
        current["updated_at_iso"] = _utc_iso()
        current = to_jsonable_python(current)
        current = json.loads(json.dumps(current, default=str))


        row.profile = current
        row.profile_version = int(current["profile_version"])

        db.commit()
        db.refresh(row)

        out = _ensure_server_fields(row.profile or {}, user_id=user_id, row=row)
        return UserProfile.model_validate(out)
    finally:
        db.close()
