"""
API routes for the Proactive Micro-Moment Recommendation system.

Endpoints
---------
POST /proactive/context-check
    Main heartbeat endpoint.  Client sends current context; server
    returns any proactive suggestions.

GET  /proactive/moments
    List all registered micro-moment definitions.

GET  /proactive/preferences/{user_id}
    Retrieve notification preferences for a user.

PUT  /proactive/preferences/{user_id}
    Create / update notification preferences.

POST /proactive/feedback
    Record user acceptance or dismissal of a suggestion.

GET  /proactive/metrics
    Acceptance-rate analytics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.recommender_service.src.proactive.proactivity_handler import (
    handle_context_update,
)
from services.recommender_service.src.proactive.schemas import (
    AcceptanceMetrics,
    ContextCheckResponse,
    MicroMomentType,
    NotificationPreferences,
    SuggestionFeedback,
    UserActivity,
    UserContextPayload,
    UserLocation,
)
from services.recommender_service.src.proactive.micro_moments import (
    get_all_moments,
    MomentDefinition,
)
from services.recommender_service.src.proactive.preference_store import (
    get_preferences,
    update_preferences,
    upsert_preferences,
)
from services.recommender_service.src.proactive.notification_manager import (
    get_acceptance_metrics,
    record_feedback,
    reset_cooldowns,
)

router = APIRouter(prefix="/proactive", tags=["proactive-micro-moments"])


# ────────────────── request / response helpers ─────────────────────

class ContextCheckRequest(BaseModel):
    """
    Thin wrapper accepted by the ``/context-check`` endpoint.
    Mirrors ``UserContextPayload`` but lets callers pass a flat
    ``location`` dict for convenience.
    """
    user_id: str
    session_id: Optional[str] = None
    timestamp: Optional[str] = None
    force: bool = Field(default=False, description="Bypass cooldowns for testing")

    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    accuracy_m: Optional[float] = None
    city: Optional[str] = None
    district: Optional[str] = None

    activity: Optional[str] = "unknown"

    current_itinerary_id: Optional[str] = None
    planned_poi_ids: Optional[List[str]] = None
    battery_pct: Optional[int] = None

    # Optional pre-fetched environment data the caller may supply
    environment: Optional[Dict[str, Any]] = None

    model_config = {"extra": "allow"}


class MomentInfo(BaseModel):
    """Serialisable view of a MomentDefinition."""
    moment_type: str
    label: str
    description: str
    priority: str
    cooldown_minutes: int
    radius_km: float
    min_confidence: float


class PreferencePatch(BaseModel):
    """Partial update body for user preferences."""
    enabled: Optional[bool] = None
    channels: Optional[List[str]] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    max_per_hour: Optional[int] = None
    max_per_day: Optional[int] = None
    disabled_moments: Optional[List[str]] = None
    min_confidence: Optional[float] = None

    model_config = {"extra": "allow"}


# ━━━━━━━━━━━━━━━━ endpoints ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/context-check", response_model=ContextCheckResponse)
def context_check(req: ContextCheckRequest):
    """
    **Main heartbeat endpoint.**

    The mobile / web client calls this whenever the user's context
    changes (location update, timer tick, activity change).  The
    response contains zero or more proactive suggestions.
    """
    import traceback
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    COLOMBO = ZoneInfo("Asia/Colombo")

    try:
        # Clear cooldowns if force mode requested
        if req.force:
            reset_cooldowns(req.user_id)

        if req.timestamp:
            ts = datetime.fromisoformat(req.timestamp)
            # Always treat the wall-clock value as Sri Lanka local time,
            # regardless of any offset the caller may have attached.
            ts = ts.replace(tzinfo=None).replace(tzinfo=COLOMBO)
        else:
            ts = datetime.now(COLOMBO)

        ctx = UserContextPayload(
            user_id=req.user_id,
            session_id=req.session_id,
            timestamp=ts,
            location=UserLocation(
                lat=req.lat,
                lng=req.lng,
                accuracy_m=req.accuracy_m,
                city=req.city,
                district=req.district,
            ),
            activity=UserActivity(req.activity or "unknown"),
            current_itinerary_id=req.current_itinerary_id,
            planned_poi_ids=req.planned_poi_ids,
            battery_pct=req.battery_pct,
        )

        # Forward any extra keys the caller attached (nearby_events, sunset_utc, …)
        env_override = req.environment or {}
        extra = req.model_extra or {}
        for key in ("nearby_events", "sunset_utc", "sunrise_utc", "next_activity_at"):
            if key in extra:
                env_override[key] = extra[key]

        return handle_context_update(ctx, environment_override=env_override or None)

    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{tb}")


@router.get("/moments", response_model=List[MomentInfo])
def list_moments():
    """Return all registered micro-moment definitions."""
    return [
        MomentInfo(
            moment_type=m.moment_type.value,
            label=m.label,
            description=m.description,
            priority=m.priority.value if hasattr(m.priority, "value") else str(m.priority),
            cooldown_minutes=m.cooldown_minutes,
            radius_km=m.radius_km,
            min_confidence=m.min_confidence,
        )
        for m in get_all_moments()
    ]


@router.get("/preferences/{user_id}", response_model=NotificationPreferences)
def get_user_preferences(user_id: str):
    """Retrieve notification preferences (creates defaults if absent)."""
    return get_preferences(user_id)


@router.put("/preferences/{user_id}", response_model=NotificationPreferences)
def set_user_preferences(user_id: str, body: PreferencePatch):
    """Create or partially update notification preferences."""
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return update_preferences(user_id, patch)


@router.post("/feedback")
def submit_feedback(body: SuggestionFeedback):
    """Record the user's accept / dismiss action on a suggestion."""
    ok = record_feedback(body)
    if not ok:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return {"status": "recorded", "suggestion_id": body.suggestion_id}


@router.get("/metrics", response_model=AcceptanceMetrics)
def metrics(user_id: Optional[str] = None):
    """Return acceptance-rate analytics, optionally filtered to one user."""
    return get_acceptance_metrics(user_id)


@router.post("/reset")
def reset(user_id: Optional[str] = None):
    """Clear cooldown / send-log so triggers can fire again immediately."""
    count = reset_cooldowns(user_id)
    return {"cleared": count, "user_id": user_id or "all"}


@router.get("/live-check")
def live_check(
    lat: float = ...,
    lng: float = ...,
    user_id: str = "auto-user",
    city: Optional[str] = None,
    force: bool = False,
):
    """
    **Convenience GET endpoint** — requires GPS coordinates from the
    device.  City name is auto-resolved via reverse geocoding (OpenWeather
    API) when not provided.

    Examples:
        GET /proactive/live-check?lat=6.9147&lng=79.9729       (GPS — city auto-resolved)
        GET /proactive/live-check?lat=6.9271&lng=79.8612&city=Colombo
        GET /proactive/live-check?lat=6.9271&lng=79.8612&force=true
    """
    import traceback
    from datetime import datetime, timezone

    try:
        # If force=true, clear cooldowns so triggers are not suppressed
        if force:
            reset_cooldowns(user_id)

        location_source = "gps"

        # If city is still missing, reverse-geocode from coords
        # (this is what happens when a mobile app sends only lat/lng)
        if not city:
            from services.recommender_service.src.proactive.proactivity_handler import (
                reverse_geocode,
            )
            geo = reverse_geocode(lat, lng)
            city = geo.get("city")
            location_source = geo.get("source", location_source)

        ctx = UserContextPayload(
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            location=UserLocation(lat=lat, lng=lng, city=city),
            activity=UserActivity.STILL,
        )

        result = handle_context_update(ctx)

        return {
            "note": "Real-time data — weather from OpenWeather, hotels from KG, sunrise/sunset computed from coordinates. "
                    "For mobile: send GPS lat/lng; city is auto-resolved via reverse geocoding.",
            "force_mode": force,
            "location_source": location_source,
            "location_used": {"lat": lat, "lng": lng, "city": city},
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "triggers_detected": [t.model_dump() for t in result.triggers_detected],
            "suggestions_count": len(result.suggestions),
            "suggestions": [s.model_dump() for s in result.suggestions],
            "suppressed_count": result.suppressed_count,
            "nearby_hotels": result.nearby_hotels,
        }
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{tb}")
