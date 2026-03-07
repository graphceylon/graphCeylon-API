"""
proactive.context_detector
~~~~~~~~~~~~~~~~~~~~~~~~~~
Context recognition module.

Analyses a ``UserContextPayload`` and returns a list of ``DetectedTrigger``
objects — one per micro-moment whose conditions are satisfied.

Detection is **rule-based + threshold-driven** so it runs in O(1) per
heartbeat with no ML model required.  Each detector method maps to exactly
one ``MicroMomentType``.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .micro_moments import MOMENT_REGISTRY, MomentDefinition, MicroMomentType
from .schemas import (
    DetectedTrigger,
    UserContextPayload,
    UserLocation,
)

COLOMBO = ZoneInfo("Asia/Colombo")


# ━━━━━━━━━━━━━━━━━━ helpers ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance between two (lat, lng) points in km."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 6_371.0 * 2 * math.asin(math.sqrt(h))


def _local_hour(ts: datetime) -> int:
    """Return the hour in Sri Lanka local time."""
    return ts.astimezone(COLOMBO).hour


def _in_hour_range(hour: int, ranges: List[Tuple[int, int]]) -> bool:
    return any(lo <= hour <= hi for lo, hi in ranges)


def _meal_label(hour: int, labels_map: Dict[Tuple[int, int], str]) -> str:
    for (lo, hi), label in labels_map.items():
        if lo <= hour <= hi:
            return label
    return "mealtime"


# ━━━━━━━━━━━━━━━━ per-moment detectors ━━━━━━━━━━━━━━━━━━━━━━━━━

def _detect_mealtime(
    ctx: UserContextPayload,
    defn: MomentDefinition,
    environment: Dict[str, Any],
) -> Optional[DetectedTrigger]:
    """
    Fire when the local hour falls inside a meal window.
    Confidence is boosted if the user is *still* (not driving).
    """
    hour = _local_hour(ctx.timestamp)
    if not defn.active_hours or not _in_hour_range(hour, defn.active_hours):
        return None

    confidence = 0.80

    meal_labels = defn.extra.get("meal_labels", {})
    # Convert string keys back to tuples if needed
    meal_label_str = "mealtime"
    for key, label in meal_labels.items():
        if isinstance(key, tuple) and key[0] <= hour <= key[1]:
            meal_label_str = label
            break

    return DetectedTrigger(
        moment_type=MicroMomentType.MEALTIME_PROXIMITY,
        confidence=min(confidence, 1.0),
        reason=f"It's {meal_label_str} near {ctx.location.city or 'your location'}.",
        metadata={
            "meal_label": meal_label_str,
            "local_hour": hour,
            "city": ctx.location.city,
        },
    )


def _detect_weather_alert(
    ctx: UserContextPayload,
    defn: MomentDefinition,
    environment: Dict[str, Any],
) -> Optional[DetectedTrigger]:
    """
    Fire when the environment dict carries an upcoming rain / storm
    forecast for the user's location.

    Expected keys in ``environment``:
      - ``weather_forecast``:  list of slot dicts with keys
        ``dt_utc``, ``rain_3h_mm``, ``condition``, ``pop``
    """
    slots: List[Dict] = environment.get("weather_forecast", [])
    if not slots:
        return None

    lookahead = defn.extra.get("lookahead_minutes", 60)
    threshold = defn.extra.get("rain_threshold_mm", 1.0)
    now = ctx.timestamp

    for slot in slots:
        try:
            dt = datetime.fromisoformat(
                slot.get("dt_utc", "").replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            continue

        delta = (dt - now).total_seconds() / 60
        if delta < 0 or delta > lookahead:
            continue

        rain_mm = float(slot.get("rain_3h_mm", 0) or 0)
        pop = float(slot.get("pop", 0) or 0)
        condition = str(slot.get("condition", "")).lower()

        if rain_mm >= threshold or pop >= 0.60 or "rain" in condition or "storm" in condition:
            minutes_until = max(1, int(delta))
            confidence = min(0.55 + pop * 0.3 + (rain_mm / 10) * 0.15, 1.0)
            return DetectedTrigger(
                moment_type=MicroMomentType.WEATHER_ALERT,
                confidence=confidence,
                reason=(
                    f"{condition.title() or 'Rain'} expected in ~{minutes_until} min "
                    f"near {ctx.location.city or 'your location'}."
                ),
                metadata={
                    "weather_condition": condition.title() or "Rain",
                    "minutes_until": minutes_until,
                    "rain_mm": rain_mm,
                    "pop": pop,
                    "city": ctx.location.city,
                },
            )
    return None


def _detect_crowd_surge(
    ctx: UserContextPayload,
    defn: MomentDefinition,
    environment: Dict[str, Any],
) -> Optional[DetectedTrigger]:
    """
    Fire when the next planned POI has a crowd index above threshold.

    Expected keys in ``environment``:
      - ``crowd_levels``:  dict mapping poi_id → {crowd_index, crowd_level, poi_title}
    """
    crowd: Dict[str, Dict] = environment.get("crowd_levels", {})
    if not crowd:
        return None

    threshold = defn.extra.get("crowd_index_threshold", 0.75)

    # Check each POI the user plans to visit
    planned = ctx.planned_poi_ids or []
    for poi_id in planned:
        info = crowd.get(poi_id, {})
        idx = float(info.get("crowd_index", 0) or 0)
        if idx >= threshold:
            confidence = min(0.6 + (idx - threshold) * 0.8, 1.0)
            return DetectedTrigger(
                moment_type=MicroMomentType.CROWD_SURGE,
                confidence=confidence,
                reason=(
                    f"{info.get('poi_title', poi_id)} is experiencing "
                    f"{info.get('crowd_level', 'high')} crowds (index {idx:.2f})."
                ),
                metadata={
                    "poi_id": poi_id,
                    "poi_name": info.get("poi_title", poi_id),
                    "crowd_index": idx,
                    "crowd_level": info.get("crowd_level", "high"),
                },
            )
    return None


def _detect_golden_hour(
    ctx: UserContextPayload,
    defn: MomentDefinition,
    environment: Dict[str, Any],
) -> Optional[DetectedTrigger]:
    """
    Fire near sunrise / sunset.

    Expected (optional) keys in ``environment``:
      - ``sunset_utc``:  ISO datetime string
      - ``sunrise_utc``: ISO datetime string

    Falls back to hour-range check if sun times are absent.
    """
    now_local = ctx.timestamp.astimezone(COLOMBO)
    hour = now_local.hour

    sunset_str = environment.get("sunset_utc")
    sunrise_str = environment.get("sunrise_utc")

    minutes_until: Optional[int] = None
    event = "sunset"

    if sunset_str:
        try:
            sunset = datetime.fromisoformat(sunset_str.replace("Z", "+00:00"))
            delta = (sunset - ctx.timestamp).total_seconds() / 60
            if 0 < delta < 90:
                minutes_until = int(delta)
                event = "sunset"
        except (ValueError, TypeError):
            pass

    if minutes_until is None and sunrise_str:
        try:
            sunrise = datetime.fromisoformat(sunrise_str.replace("Z", "+00:00"))
            delta = (sunrise - ctx.timestamp).total_seconds() / 60
            if 0 < delta < 60:
                minutes_until = int(delta)
                event = "sunrise"
        except (ValueError, TypeError):
            pass

    # Fallback: use hour ranges
    if minutes_until is None:
        if defn.active_hours and _in_hour_range(hour, defn.active_hours):
            minutes_until = 30  # rough guess
            event = "sunset" if hour >= 15 else "sunrise"
        else:
            return None

    confidence = 0.70 if minutes_until <= 45 else 0.55

    return DetectedTrigger(
        moment_type=MicroMomentType.GOLDEN_HOUR,
        confidence=confidence,
        reason=f"{event.title()} in ~{minutes_until} min near {ctx.location.city or 'your location'}.",
        metadata={
            "event": event,
            "minutes_until": minutes_until,
            "city": ctx.location.city,
        },
    )


def _detect_transit_window(
    ctx: UserContextPayload,
    defn: MomentDefinition,
    environment: Dict[str, Any],
) -> Optional[DetectedTrigger]:
    """
    Fire when the user has an idle gap of ≥ N minutes before the next
    scheduled itinerary item.

    Expected keys in ``environment``:
      - ``next_activity_at``:  ISO datetime of the next planned stop
    """
    next_at_str = environment.get("next_activity_at")
    if not next_at_str:
        return None

    try:
        next_at = datetime.fromisoformat(next_at_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None

    gap_minutes = (next_at - ctx.timestamp).total_seconds() / 60
    min_gap = defn.extra.get("min_gap_minutes", 30)

    if gap_minutes < min_gap:
        return None

    confidence = 0.70 if gap_minutes >= 60 else 0.60

    return DetectedTrigger(
        moment_type=MicroMomentType.TRANSIT_WINDOW,
        confidence=min(confidence, 1.0),
        reason=f"You have ~{int(gap_minutes)} min free before your next stop.",
        metadata={
            "gap_minutes": int(gap_minutes),
            "next_activity_at": next_at_str,
        },
    )


def _detect_cultural_event(
    ctx: UserContextPayload,
    defn: MomentDefinition,
    environment: Dict[str, Any],
) -> Optional[DetectedTrigger]:
    """
    Fire when there is a cultural event happening nearby.

    Expected keys in ``environment``:
      - ``nearby_events``:  list of
            {name, lat, lng, category, start_utc, end_utc}
    """
    events: List[Dict] = environment.get("nearby_events", [])
    if not events:
        return None

    radius = defn.radius_km
    user_pos = (ctx.location.lat, ctx.location.lng)
    now = ctx.timestamp

    for ev in events:
        ev_lat = ev.get("lat")
        ev_lng = ev.get("lng")
        if ev_lat is None or ev_lng is None:
            continue

        dist = _haversine_km(user_pos, (float(ev_lat), float(ev_lng)))
        if dist > radius:
            continue

        # Check the event is currently active
        try:
            start = datetime.fromisoformat(ev.get("start_utc", "").replace("Z", "+00:00"))
            end = datetime.fromisoformat(ev.get("end_utc", "").replace("Z", "+00:00"))
            if not (start <= now <= end):
                continue
        except (ValueError, TypeError):
            pass  # if no times, assume active

        confidence = max(0.55, min(0.90, 1.0 - dist / radius))

        return DetectedTrigger(
            moment_type=MicroMomentType.CULTURAL_EVENT,
            confidence=confidence,
            reason=f"{ev.get('name', 'An event')} is happening {dist:.1f} km away in {ctx.location.city or 'your area'}.",
            metadata={
                "event_name": ev.get("name"),
                "distance_km": round(dist, 2),
                "city": ctx.location.city,
                "category": ev.get("category"),
            },
        )
    return None


# ━━━━━━━━━━━━━━━━ dispatcher mapping ━━━━━━━━━━━━━━━━━━━━━━━━━━━

_DETECTOR_MAP = {
    MicroMomentType.MEALTIME_PROXIMITY: _detect_mealtime,
    MicroMomentType.WEATHER_ALERT: _detect_weather_alert,
    MicroMomentType.CROWD_SURGE: _detect_crowd_surge,
    MicroMomentType.GOLDEN_HOUR: _detect_golden_hour,
    MicroMomentType.TRANSIT_WINDOW: _detect_transit_window,
    MicroMomentType.CULTURAL_EVENT: _detect_cultural_event,
}


# ━━━━━━━━━━━━━━━ public entry point ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_micro_moments(
    ctx: UserContextPayload,
    environment: Dict[str, Any] | None = None,
) -> List[DetectedTrigger]:
    """
    Run **all** registered detectors against the given user context
    and return every trigger whose confidence exceeds the moment's
    ``min_confidence``.

    Parameters
    ----------
    ctx : UserContextPayload
        The latest heartbeat / context update from the client.
    environment : dict, optional
        Pre-fetched environmental data (weather forecast, crowd levels,
        nearby events, sunset time, etc.).  Each detector documents the
        keys it expects.

    Returns
    -------
    list[DetectedTrigger]
        Zero or more triggers, sorted by confidence descending.
    """
    environment = environment or {}
    triggers: List[DetectedTrigger] = []

    for moment_type, detector_fn in _DETECTOR_MAP.items():
        defn = MOMENT_REGISTRY.get(moment_type)
        if defn is None:
            continue

        trigger = detector_fn(ctx, defn, environment)
        if trigger is not None and trigger.confidence >= defn.min_confidence:
            triggers.append(trigger)

    # highest confidence first
    triggers.sort(key=lambda t: t.confidence, reverse=True)
    return triggers
