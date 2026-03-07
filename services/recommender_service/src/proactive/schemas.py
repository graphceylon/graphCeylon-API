"""
proactive.schemas
~~~~~~~~~~~~~~~~~
Pydantic models shared across the micro-moment sub-system.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(timezone.utc)


# ────────────────────────────── enums ──────────────────────────────

class MicroMomentType(str, Enum):
    """The six recognised micro-moment contexts."""
    MEALTIME_PROXIMITY = "mealtime_proximity"
    WEATHER_ALERT = "weather_alert"
    CROWD_SURGE = "crowd_surge"
    GOLDEN_HOUR = "golden_hour"
    TRANSIT_WINDOW = "transit_window"
    CULTURAL_EVENT = "cultural_event"


class NotificationChannel(str, Enum):
    PUSH = "push"
    IN_APP = "in_app"
    SMS = "sms"
    EMAIL = "email"


class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


# ────────────────────────────── inputs ─────────────────────────────

class UserLocation(BaseModel):
    """GPS snapshot of the traveller."""
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    accuracy_m: Optional[float] = None
    city: Optional[str] = None
    district: Optional[str] = None


class UserActivity(str, Enum):
    """Coarse activity label from the client device."""
    STILL = "still"
    WALKING = "walking"
    DRIVING = "driving"
    IN_VEHICLE = "in_vehicle"
    UNKNOWN = "unknown"


class UserContextPayload(BaseModel):
    """
    Everything the client pushes each heartbeat / context-update.
    This is the **single input** to the context-detection pipeline.
    """
    user_id: str
    session_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=_utcnow)

    location: UserLocation
    activity: UserActivity = UserActivity.UNKNOWN

    # optional extras the client may attach
    current_itinerary_id: Optional[str] = None
    planned_poi_ids: Optional[List[str]] = None
    battery_pct: Optional[int] = None

    model_config = {"extra": "allow"}


# ────────────────────────── detected trigger ───────────────────────

class DetectedTrigger(BaseModel):
    """
    Produced by `context_detector` when a micro-moment is recognised.
    """
    moment_type: MicroMomentType
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., description="Human-readable explanation")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=_utcnow)


# ────────────────────────── suggestion / push ──────────────────────

class ProactiveSuggestion(BaseModel):
    """
    A complete recommendation pushed to the user in response to a
    detected micro-moment.
    """
    suggestion_id: str
    moment_type: MicroMomentType
    title: str
    body: str
    priority: NotificationPriority = NotificationPriority.MEDIUM
    channel: NotificationChannel = NotificationChannel.IN_APP

    # what we are recommending
    recommended_pois: List[Dict[str, Any]] = Field(default_factory=list)

    # provenance
    trigger: DetectedTrigger
    user_id: str
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: Optional[datetime] = None
    status: SuggestionStatus = SuggestionStatus.PENDING


# ────────────────────── user notification prefs ────────────────────

class NotificationPreferences(BaseModel):
    """
    Per-user settings that control proactive delivery.
    Stored and retrieved by `preference_store`.
    """
    user_id: str
    enabled: bool = True
    channels: List[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.IN_APP],
    )
    quiet_hours_start: Optional[int] = Field(
        default=22,
        description="Hour (0-23, local time) when notifications pause.",
    )
    quiet_hours_end: Optional[int] = Field(
        default=7,
        description="Hour (0-23, local time) when notifications resume.",
    )
    max_per_hour: int = Field(
        default=3,
        description="Rate-limit: max proactive pushes per hour.",
    )
    max_per_day: int = Field(
        default=12,
        description="Rate-limit: max proactive pushes per day.",
    )
    # per-moment opt-out
    disabled_moments: List[MicroMomentType] = Field(default_factory=list)
    # minimum confidence to push
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    model_config = {"extra": "allow"}


# ──────────────────── feedback / acceptance tracking ───────────────

class SuggestionFeedback(BaseModel):
    """User action on a previously-delivered suggestion."""
    suggestion_id: str
    user_id: str
    action: SuggestionStatus  # accepted | dismissed
    feedback_text: Optional[str] = None
    acted_at: datetime = Field(default_factory=_utcnow)


# ──────────────── API response wrappers ────────────────────────────

class ContextCheckResponse(BaseModel):
    """Returned by the /proactive/context-check endpoint."""
    triggers_detected: List[DetectedTrigger]
    suggestions: List[ProactiveSuggestion]
    suppressed_count: int = Field(
        default=0,
        description="Number of triggers suppressed by user preferences / rate-limits.",
    )
    nearby_hotels: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Hotels in the user's current city, fetched from KG.",
    )
    environment: Dict[str, Any] = Field(
        default_factory=dict,
        description="All collected environmental data: weather_forecast, sunrise/sunset, crowd_levels, reverse_geocode, etc.",
    )


class AcceptanceMetrics(BaseModel):
    """Aggregate metrics returned by the analytics endpoint."""
    total_sent: int = 0
    total_accepted: int = 0
    total_dismissed: int = 0
    acceptance_rate: float = 0.0
    by_moment: Dict[str, Dict[str, int]] = Field(default_factory=dict)
