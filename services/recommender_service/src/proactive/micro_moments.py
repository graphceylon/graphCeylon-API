"""
proactive.micro_moments
~~~~~~~~~~~~~~~~~~~~~~~
Registry of the six distinct micro-moment contexts.

Each context carries:
  • an identifier (MicroMomentType enum value)
  • a human-readable description
  • detection parameters (thresholds, time windows, etc.)
  • a template for the push notification copy

New moments can be added by appending to MOMENT_REGISTRY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .schemas import MicroMomentType, NotificationPriority


@dataclass(frozen=True)
class MomentDefinition:
    """Static definition of a single micro-moment context."""

    moment_type: MicroMomentType
    label: str
    description: str
    priority: NotificationPriority

    # ── Detection parameters ──
    # Time windows (hour ranges in local time, inclusive)
    active_hours: Optional[List[Tuple[int, int]]] = None

    # Minimum confidence from context_detector to fire
    min_confidence: float = 0.50

    # Cooldown in minutes before the same moment can fire again for the
    # same user (prevents spamming)
    cooldown_minutes: int = 30

    # Maximum radius (km) for location-aware moments
    radius_km: float = 5.0

    # ── Notification template ──
    notification_title_template: str = ""
    notification_body_template: str = ""

    # Extra config (moment-specific knobs)
    extra: Dict = field(default_factory=dict)


# ━━━━━━━━━━━━━━━━━━ MOMENT REGISTRY ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MOMENT_REGISTRY: Dict[MicroMomentType, MomentDefinition] = {}


def _register(m: MomentDefinition) -> MomentDefinition:
    MOMENT_REGISTRY[m.moment_type] = m
    return m


# 1 ── Mealtime Proximity ──────────────────────────────────────────
_register(MomentDefinition(
    moment_type=MicroMomentType.MEALTIME_PROXIMITY,
    label="Mealtime Near You",
    description=(
        "Detects when the user is near a food zone during typical meal "
        "hours and suggests top-rated nearby restaurants or street-food "
        "spots."
    ),
    priority=NotificationPriority.MEDIUM,
    active_hours=[(6, 9), (11, 14), (18, 21)],  # breakfast, lunch, dinner
    cooldown_minutes=60,
    radius_km=2.0,
    notification_title_template="🍽️ Hungry near {city}?",
    notification_body_template=(
        "It's {meal_label} and there are {count} great spots within "
        "{radius_km} km. Tap to see suggestions!"
    ),
    extra={"meal_labels": {(6, 9): "breakfast time", (11, 14): "lunchtime", (18, 21): "dinner time"}},
))

# 2 ── Weather Alert ────────────────────────────────────────────────
_register(MomentDefinition(
    moment_type=MicroMomentType.WEATHER_ALERT,
    label="Weather Change Ahead",
    description=(
        "Triggers when adverse weather (rain, storm) is forecast within "
        "the next 15-60 minutes at the user's location, suggesting "
        "indoor attractions or shelter."
    ),
    priority=NotificationPriority.HIGH,
    cooldown_minutes=45,
    radius_km=5.0,
    notification_title_template="🌧️ Rain expected near {city}!",
    notification_body_template=(
        "{weather_condition} expected in ~{minutes_until} min. "
        "Here are {count} indoor alternatives nearby."
    ),
    extra={"lookahead_minutes": 60, "rain_threshold_mm": 1.0},
))

# 3 ── Crowd Surge ─────────────────────────────────────────────────
_register(MomentDefinition(
    moment_type=MicroMomentType.CROWD_SURGE,
    label="Crowd Alert",
    description=(
        "Fires when the user's next planned POI is experiencing "
        "unusually high crowd levels, offering quieter alternatives."
    ),
    priority=NotificationPriority.HIGH,
    cooldown_minutes=30,
    radius_km=10.0,
    notification_title_template="⚠️ {poi_name} is crowded right now",
    notification_body_template=(
        "Crowd index at {poi_name} is {crowd_level}. "
        "Consider {count} less-crowded alternatives nearby."
    ),
    extra={"crowd_index_threshold": 0.75},
))

# 4 ── Golden Hour / Sunset ────────────────────────────────────────
_register(MomentDefinition(
    moment_type=MicroMomentType.GOLDEN_HOUR,
    label="Golden Hour Opportunity",
    description=(
        "Suggests scenic viewpoints, beaches, or photo-worthy spots "
        "when sunset/sunrise golden-hour is approaching at the user's "
        "location."
    ),
    priority=NotificationPriority.LOW,
    active_hours=[(5, 7), (16, 19)],  # sunrise window, sunset window
    cooldown_minutes=120,
    radius_km=8.0,
    notification_title_template="🌅 Golden hour near {city}!",
    notification_body_template=(
        "Sunset is in ~{minutes_until} min. Check out {count} scenic "
        "spots near you for the perfect photo."
    ),
    extra={"scenic_tags": ["viewpoint", "beach", "scenic", "photography", "sunset"]},
))

# 5 ── Transit Window ──────────────────────────────────────────────
_register(MomentDefinition(
    moment_type=MicroMomentType.TRANSIT_WINDOW,
    label="Free Time Nearby",
    description=(
        "Detects idle gaps (≥30 min) between planned itinerary "
        "activities and suggests quick experiences nearby that fit "
        "the window."
    ),
    priority=NotificationPriority.LOW,
    cooldown_minutes=60,
    radius_km=3.0,
    notification_title_template="⏳ Got {gap_minutes} min free?",
    notification_body_template=(
        "You have ~{gap_minutes} min before your next stop. "
        "Here are {count} quick things to do nearby."
    ),
    extra={"min_gap_minutes": 30, "max_suggestion_duration_minutes": 45},
))

# 6 ── Cultural Event Nearby ───────────────────────────────────────
_register(MomentDefinition(
    moment_type=MicroMomentType.CULTURAL_EVENT,
    label="Cultural Event Nearby",
    description=(
        "Alerts the user when a cultural festival, market, or ceremony "
        "is happening within range of their current location."
    ),
    priority=NotificationPriority.MEDIUM,
    cooldown_minutes=120,
    radius_km=10.0,
    notification_title_template="🎭 {event_name} happening near you!",
    notification_body_template=(
        "{event_name} is on right now in {city}, just {distance_km:.1f} km "
        "away. Tap to add it to your plan."
    ),
    extra={"event_categories": ["festival", "market", "ceremony", "poya", "perahera"]},
))


# ━━━━━━━━━━━ helpers ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_all_moments() -> List[MomentDefinition]:
    """Return all registered micro-moment definitions."""
    return list(MOMENT_REGISTRY.values())


def get_moment(moment_type: MicroMomentType) -> Optional[MomentDefinition]:
    """Lookup a single moment definition."""
    return MOMENT_REGISTRY.get(moment_type)
