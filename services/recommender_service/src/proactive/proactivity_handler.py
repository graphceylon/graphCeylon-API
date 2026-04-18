"""
proactive.proactivity_handler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Orchestration layer that ties together:

    context_detector  →  recommendation lookup  →  notification_manager

When the client sends a context heartbeat, this handler:

1. Calls ``context_detector.detect_micro_moments`` to identify triggers.
2. Filters triggers through the user's ``NotificationPreferences``.
3. For each surviving trigger, queries the itinerary / recommendation /
   weather / crowd modules for quick, context-aware POI suggestions.
4. Packages results as ``ProactiveSuggestion`` objects via
   ``notification_manager``.

This is the **single entry-point** called by the API route.
"""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .context_detector import detect_micro_moments, _haversine_km
from .micro_moments import MOMENT_REGISTRY, MicroMomentType
from .notification_manager import build_suggestion, filter_triggers
from .preference_store import get_preferences
from .schemas import (
    ContextCheckResponse,
    DetectedTrigger,
    NotificationPreferences,
    ProactiveSuggestion,
    UserContextPayload,
)

logger = logging.getLogger(__name__)

KG_BASE_URL = os.getenv("KG_BASE_URL", "http://localhost:8000").rstrip("/")
KG_HOTEL_SEARCH_PATH = "/hotels/orchestrator/call/hotels/search"
KG_RESTAURANT_SEARCH_PATH = "/restaurants/orchestrator/call/restaurants"


# ━━━━━━━━━━━━━ sunrise / sunset calculation ━━━━━━━━━━━━━━━━━━━

def _compute_sun_times(lat: float, lng: float) -> Dict[str, str]:
    """
    Compute approximate sunrise / sunset UTC times for today at (lat, lng)
    using the standard solar equations (accurate to ~2 min).
    No external API needed.
    """
    from datetime import date, timedelta
    import math

    today = date.today()
    day_of_year = today.timetuple().tm_yday

    # solar noon approximation
    lng_hour = lng / 15.0

    # sunrise
    t_rise = day_of_year + (6 - lng_hour) / 24.0
    # sunset
    t_set = day_of_year + (18 - lng_hour) / 24.0

    # Sun's mean anomaly
    def sun_mean_anomaly(t):
        return 0.9856 * t - 3.289

    def sun_longitude(m):
        l = m + 1.916 * math.sin(math.radians(m)) + 0.020 * math.sin(math.radians(2 * m)) + 282.634
        return l % 360

    def sun_right_ascension(l):
        ra = math.degrees(math.atan(0.91764 * math.tan(math.radians(l))))
        ra = ra % 360
        l_q = (l // 90) * 90
        ra_q = (ra // 90) * 90
        ra = ra + (l_q - ra_q)
        return ra / 15.0  # in hours

    def sun_declination(l):
        sin_dec = 0.39782 * math.sin(math.radians(l))
        cos_dec = math.cos(math.asin(sin_dec))
        return sin_dec, cos_dec

    def hour_angle(sin_dec, cos_dec, lat_r, zenith=90.833):
        cos_h = (math.cos(math.radians(zenith)) - sin_dec * math.sin(lat_r)) / (cos_dec * math.cos(lat_r))
        if cos_h > 1 or cos_h < -1:
            return None
        return cos_h

    lat_r = math.radians(lat)
    results = {}

    for label, t_approx, is_rise in [("sunrise_utc", t_rise, True), ("sunset_utc", t_set, False)]:
        m = sun_mean_anomaly(t_approx)
        l = sun_longitude(m)
        ra = sun_right_ascension(l)
        sin_dec, cos_dec = sun_declination(l)
        cos_h = hour_angle(sin_dec, cos_dec, lat_r)
        if cos_h is None:
            continue
        h = math.degrees(math.acos(cos_h))
        if is_rise:
            h = 360 - h
        h_hours = h / 15.0
        local_t = h_hours + ra - 0.06571 * t_approx - 6.622
        utc_t = (local_t - lng_hour) % 24
        hour_int = int(utc_t)
        minute_int = int((utc_t - hour_int) * 60)
        dt = datetime(today.year, today.month, today.day, hour_int, minute_int, 0, tzinfo=timezone.utc)
        results[label] = dt.isoformat()

    return results


# geo_locate_by_ip() — REMOVED
# IP-based geolocation was inaccurate (returns ISP hub, not device
# location).  All location resolution now uses device GPS coordinates
# + reverse_geocode() via the OpenWeather API.


def reverse_geocode(lat: float, lng: float) -> Dict[str, Any]:
    """
    Resolve a city / locality name from GPS coordinates.

    Uses the **OpenWeather Reverse Geocoding API** (same key we
    already have) so no extra dependency is needed.
    Endpoint: ``GET https://api.openweathermap.org/geo/1.0/reverse``

    Falls back to the free Nominatim (OpenStreetMap) API when
    the OpenWeather call fails.

    Returns ``{"city": ..., "district": ..., "country": ...}``
    or an empty dict on total failure.
    """
    import urllib.request
    import json

    # ── attempt 1: OpenWeather reverse geocoding ──────────────
    try:
        from configs.recommender_service.config import OPENWEATHER_API_KEY

        url = (
            f"https://api.openweathermap.org/geo/1.0/reverse"
            f"?lat={lat}&lon={lng}&limit=1&appid={OPENWEATHER_API_KEY}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "graphCeylon/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        if data and isinstance(data, list) and len(data) > 0:
            entry = data[0]
            return {
                "city": entry.get("name"),
                "district": entry.get("state"),
                "country": entry.get("country"),
                "source": "openweather_reverse_geocode",
            }
    except Exception as exc:
        logger.warning("OpenWeather reverse geocode failed: %s", exc)

    # ── attempt 2: Nominatim (OpenStreetMap) ──────────────────
    try:
        url = (
            f"https://nominatim.openstreetmap.org/reverse"
            f"?lat={lat}&lon={lng}&format=jsonv2&zoom=10"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "graphCeylon/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        addr = data.get("address", {})
        city = (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("suburb")
            or data.get("name")
        )
        return {
            "city": city,
            "district": addr.get("state_district") or addr.get("state"),
            "country": addr.get("country_code", "").upper(),
            "source": "nominatim_reverse_geocode",
        }
    except Exception as exc:
        logger.warning("Nominatim reverse geocode failed: %s", exc)

    return {}


# ━━━━━━━━━━━━━ environment enrichment helpers ━━━━━━━━━━━━━━━━━━

def _fetch_weather_environment(
    city: str | None,
    lat: float,
    lng: float,
) -> Dict[str, Any]:
    """
    Best-effort fetch of upcoming weather slots from the existing
    weather module.  Returns an empty dict on failure so the handler
    degrades gracefully.
    """
    if not city:
        return {}
    try:
        from services.recommender_service.src.weather.openweather import (
            fetch_openweather_for_city_and_day,
        )
        from datetime import date

        result = fetch_openweather_for_city_and_day(
            city=city,
            country="LK",
            target_date=date.today(),
        )
        slots = result.get("slots", [])
        return {"weather_forecast": slots}
    except Exception as exc:
        logger.warning("Weather fetch failed for proactive handler: %s", exc)
        return {}


def _fetch_nearby_hotels(
    city: str | None,
    *,
    limit: int = 10,
    timeout: float = 15.0,
) -> List[Dict[str, Any]]:
    """
    Best-effort fetch of hotels in the resolved city from the KG
    hotel search endpoint.  Returns an empty list on failure so the
    handler degrades gracefully.
    """
    if not city:
        return []
    try:
        import httpx

        url = f"{KG_BASE_URL}{KG_HOTEL_SEARCH_PATH}"
        body = {
            "intent": "info_accommodation",
            "raw_text": f"hotels in {city}",
            "user_id": "proactive-system",
            "session_id": "proactive-heartbeat",
            "city": city,
            "limit": limit,
        }
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=body)
            r.raise_for_status()
            data = r.json()

        items = data.get("items") or []
        logger.info("Fetched %d hotels for city=%s", len(items), city)
        return items
    except Exception as exc:
        logger.warning("Hotel fetch for '%s' failed: %s", city, exc)
        return []


def _fetch_nearby_restaurants(
    city: str | None,
    *,
    limit: int = 5,
    timeout: float = 3.0,
) -> List[Dict[str, Any]]:
    """
    Fast-fail restaurant fetch for proactive heartbeat.
    Never block the whole context-check for too long.
    """
    if not city:
        return []

    try:
        import httpx

        url = f"{KG_BASE_URL}{KG_RESTAURANT_SEARCH_PATH}"
        body = {
            "city": city,
            "country": "Sri Lanka",
            "poi_name": None,
            "days": 1,
            "tags": [],
            "user_id": "proactive-system",
            "session_id": "proactive-heartbeat",
            "query": f"What are the best restaurants in {city}?",
        }

        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=body)
            r.raise_for_status()
            data = r.json()

        items = data.get("items") or data.get("restaurants") or []
        logger.info("Fetched %d restaurants for city=%s", len(items), city)
        return items[:limit]

    except httpx.TimeoutException:
        logger.warning("Restaurant fetch for '%s' timed out after %.1fs", city, timeout)
        return []
    except Exception as exc:
        logger.warning("Restaurant fetch for '%s' failed: %s", city, exc)
        return []


def _fetch_crowd_environment(
    poi_ids: List[str] | None,
) -> Dict[str, Any]:
    """
    Best-effort fetch of crowd levels for planned POIs.
    Returns ``{crowd_levels: {poi_id: {...}}}`` or empty dict.
    """
    if not poi_ids:
        return {}
    try:
        from services.recommender_service.src.crowd.inference.crowd_model import (
            forecast_poi_crowd,
        )
        from datetime import date

        levels: Dict[str, Dict] = {}
        for pid in poi_ids[:5]:  # cap to avoid latency
            try:
                result = forecast_poi_crowd(
                    poi_id=pid,
                    month_start=date.today().replace(day=1),
                    total_foreign_arrivals_month=0,  # will use defaults
                )
                if result and isinstance(result, dict):
                    levels[pid] = {
                        "crowd_index": result.get("crowd_index_mean", 0),
                        "crowd_level": result.get("crowd_level", "unknown"),
                        "poi_title": result.get("poi_title", pid),
                    }
            except Exception:
                continue
        return {"crowd_levels": levels} if levels else {}
    except Exception as exc:
        logger.warning("Crowd fetch failed for proactive handler: %s", exc)
        return {}


def build_environment(ctx: UserContextPayload) -> Dict[str, Any]:
    """
    Collect all environmental data needed by the detectors.
    Each sub-fetch is isolated so one failure doesn't block others.

    If location.city is missing (common when a mobile app sends only
    GPS coords), this function automatically reverse-geocodes the
    coordinates to resolve the city name before calling weather APIs.
    """
    env: Dict[str, Any] = {}

    # ── Auto-resolve city from GPS coords if not provided ─────
    if not ctx.location.city and ctx.location.lat and ctx.location.lng:
        try:
            geo = reverse_geocode(ctx.location.lat, ctx.location.lng)
            if geo.get("city"):
                ctx.location.city = geo["city"]
                logger.info(
                    "Reverse-geocoded (%s, %s) → %s (%s)",
                    ctx.location.lat, ctx.location.lng,
                    geo["city"], geo.get("source"),
                )
                env["reverse_geocode"] = geo
        except Exception as exc:
            logger.warning("Reverse geocode failed: %s", exc)

    # Weather (real OpenWeather API call)
    env.update(_fetch_weather_environment(
        city=ctx.location.city,
        lat=ctx.location.lat,
        lng=ctx.location.lng,
    ))

    # Crowd levels for planned POIs (real crowd model)
    env.update(_fetch_crowd_environment(ctx.planned_poi_ids))

    # Sunrise / Sunset (computed from lat/lng, no API needed)
    try:
        sun = _compute_sun_times(ctx.location.lat, ctx.location.lng)
        env.update(sun)
    except Exception as exc:
        logger.warning("Sun-time computation failed: %s", exc)

    # Nearby hotels & restaurants — only during meal and golden-hour windows
    # Breakfast 6-9, Lunch 11-14, Sunset 16-19, Dinner 18-21
    from zoneinfo import ZoneInfo
    local_hour = ctx.timestamp.astimezone(ZoneInfo("Asia/Colombo")).hour
    _HOTEL_HOURS = [(5, 9), (11, 14), (16, 21)]  # sunrise/breakfast, lunch, sunset/dinner
    in_hotel_window = any(lo <= local_hour <= hi for lo, hi in _HOTEL_HOURS)

    if in_hotel_window:
        try:
            hotels = _fetch_nearby_hotels(ctx.location.city)
            env["nearby_hotels"] = hotels
        except Exception as exc:
            logger.warning("Hotel environment fetch failed: %s", exc)
            env["nearby_hotels"] = []
        
        try:
            restaurants = _fetch_nearby_restaurants(ctx.location.city)
            env["nearby_restaurants"] = restaurants
        except Exception as exc:
            logger.warning("Restaurant environment fetch failed: %s", exc)
            env["nearby_restaurants"] = []
    else:
        env["nearby_hotels"] = []
        env["nearby_restaurants"] = []

    # Clients may attach extra environment keys directly
    # (e.g., nearby_events, sunset_utc, next_activity_at)
    extra = getattr(ctx, "__pydantic_extra__", None) or {}
    for key in ("nearby_events", "sunset_utc", "sunrise_utc", "next_activity_at"):
        if key in extra:
            env[key] = extra[key]

    return env


# ━━━━━━━━ POI resolver (per moment type) ━━━━━━━━━━━━━━━━━━━━━━

def _resolve_pois_for_trigger(
    trigger: DetectedTrigger,
    ctx: UserContextPayload,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Query the KG / POI layer for context-aware suggestions matching
    the detected micro-moment.

    Each branch maps a moment type to an appropriate POI lookup
    strategy using the existing normalisation and KG modules.
    """
    try:
        from services.recommender_service.src.poi.normalize import (
            load_attractions_index,
        )
        index = load_attractions_index()
    except Exception as exc:
        logger.warning("POI index load failed: %s", exc)
        return []

    user_pos = (ctx.location.lat, ctx.location.lng)
    defn = MOMENT_REGISTRY.get(trigger.moment_type)
    radius = defn.radius_km if defn else 5.0

    # Collect candidates within radius
    nearby: List[Dict[str, Any]] = []
    for key, record in index.items():
        rlat = record.get("latitude") or record.get("lat")
        rlng = record.get("longitude") or record.get("lng") or record.get("lon")
        if rlat is None or rlng is None:
            continue
        try:
            dist = _haversine_km(user_pos, (float(rlat), float(rlng)))
        except (TypeError, ValueError):
            continue
        if dist <= radius:
            record_copy = dict(record)
            record_copy["_distance_km"] = round(dist, 2)
            nearby.append(record_copy)

    if not nearby:
        return []

    # Sort by distance
    nearby.sort(key=lambda r: r["_distance_km"])

    # ── moment-specific filtering ──
    mt = trigger.moment_type

    if mt == MicroMomentType.MEALTIME_PROXIMITY:
        # prefer restaurants / food-tagged POIs
        food_keywords = {"restaurant", "food", "cafe", "bakery", "street food", "dining"}
        scored = []
        for r in nearby:
            cats = {c.lower() for c in (r.get("categories") or [])}
            tags = {t.lower() for t in (r.get("tags") or [])}
            name_lower = (r.get("name") or "").lower()
            is_food = bool(cats & food_keywords) or bool(tags & food_keywords) or any(fw in name_lower for fw in food_keywords)
            scored.append((0 if is_food else 1, r["_distance_km"], r))
        scored.sort(key=lambda x: (x[0], x[1]))
        return [r for _, _, r in scored[:limit]]

    if mt == MicroMomentType.WEATHER_ALERT:
        # prefer indoor POIs
        indoor_keywords = {"museum", "gallery", "temple", "mall", "shopping", "indoor", "cinema"}
        scored = []
        for r in nearby:
            cats = {c.lower() for c in (r.get("categories") or [])}
            tags = {t.lower() for t in (r.get("tags") or [])}
            is_indoor = bool(cats & indoor_keywords) or bool(tags & indoor_keywords)
            scored.append((0 if is_indoor else 1, r["_distance_km"], r))
        scored.sort(key=lambda x: (x[0], x[1]))
        return [r for _, _, r in scored[:limit]]

    if mt == MicroMomentType.CROWD_SURGE:
        # return alternatives that are NOT the crowded POI
        crowded_id = trigger.metadata.get("poi_id")
        alternatives = [r for r in nearby if r.get("attraction_id") != crowded_id and r.get("poi_id") != crowded_id]
        return alternatives[:limit]

    if mt == MicroMomentType.GOLDEN_HOUR:
        scenic_tags = set(defn.extra.get("scenic_tags", [])) if defn else {"scenic", "viewpoint", "beach"}
        scored = []
        for r in nearby:
            cats = {c.lower() for c in (r.get("categories") or [])}
            tags = {t.lower() for t in (r.get("tags") or [])}
            is_scenic = bool(cats & scenic_tags) or bool(tags & scenic_tags)
            scored.append((0 if is_scenic else 1, r["_distance_km"], r))
        scored.sort(key=lambda x: (x[0], x[1]))
        return [r for _, _, r in scored[:limit]]

    if mt == MicroMomentType.TRANSIT_WINDOW:
        # any quick experience nearby
        return nearby[:limit]

    if mt == MicroMomentType.CULTURAL_EVENT:
        return nearby[:limit]

    return nearby[:limit]


# ━━━━━━━━━━━━━━ main entry point ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def handle_context_update(
    ctx: UserContextPayload,
    environment_override: Dict[str, Any] | None = None,
) -> ContextCheckResponse:
    """
    **Primary entry-point** for the proactive micro-moment system.

    1. Build / merge environmental data.
    2. Run all detectors → list of ``DetectedTrigger``.
    3. Filter through user notification preferences.
    4. Resolve POIs for each surviving trigger.
    5. Build ``ProactiveSuggestion`` objects.

    Parameters
    ----------
    ctx : UserContextPayload
        Latest context heartbeat from the client.
    environment_override : dict, optional
        If provided, merged **on top of** the auto-fetched environment
        (useful for testing or when the caller already has weather data).

    Returns
    -------
    ContextCheckResponse
    """
    # 1. environment
    env = build_environment(ctx)
    if environment_override:
        env.update(environment_override)

    # 2. detect
    triggers = detect_micro_moments(ctx, env)
    logger.info(
        "User %s: %d raw triggers detected",
        ctx.user_id,
        len(triggers),
    )

    # 3. filter
    prefs = get_preferences(ctx.user_id)
    allowed, suppressed_count = filter_triggers(triggers, prefs)
    logger.info(
        "User %s: %d triggers allowed, %d suppressed",
        ctx.user_id,
        len(allowed),
        suppressed_count,
    )

    # 4 + 5. resolve POIs → build suggestions
    suggestions: List[ProactiveSuggestion] = []
    for trigger in allowed:
        pois = _resolve_pois_for_trigger(trigger, ctx)
        suggestion = build_suggestion(
            trigger=trigger,
            recommended_pois=pois,
            user_id=ctx.user_id,
        )
        suggestions.append(suggestion)

    return ContextCheckResponse(
        triggers_detected=triggers,  # all raw triggers (for transparency)
        suggestions=suggestions,
        suppressed_count=suppressed_count,
        nearby_hotels=env.get("nearby_hotels", []),
        environment=env,
    )
