"""
Test script for the 6 Micro-Moment Context Triggers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Run from the recommender_service dir with PYTHONPATH set:

    cd services/recommender_service
    $env:PYTHONPATH="../.."
    python -m src.proactive.test_micro_moments                              # simulated data
    python -m src.proactive.test_micro_moments --live                       # REAL weather + GPS (default: Colombo)
    python -m src.proactive.test_micro_moments --live --lat=7.29 --lng=80.63  # custom GPS coords

Each test simulates a realistic Sri Lanka tourism scenario.
The --live flag fetches real OpenWeather data using GPS coordinates
and reverse geocoding (no IP-based location).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from src.proactive.context_detector import detect_micro_moments
from src.proactive.schemas import (
    MicroMomentType,
    UserActivity,
    UserContextPayload,
    UserLocation,
)

COLOMBO = ZoneInfo("Asia/Colombo")
PASS = "\033[92m✔ PASS\033[0m"
FAIL = "\033[91m✘ FAIL\033[0m"

results = {"passed": 0, "failed": 0}


def _header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _check(label: str, triggers, expected_type: MicroMomentType):
    found = [t for t in triggers if t.moment_type == expected_type]
    if found:
        t = found[0]
        print(f"  {PASS} {label}")
        print(f"       Confidence : {t.confidence:.2f}")
        print(f"       Reason     : {t.reason}")
        print(f"       Metadata   : {json.dumps(t.metadata, default=str, indent=2)}")
        results["passed"] += 1
    else:
        print(f"  {FAIL} {label}  (no trigger of type {expected_type.value})")
        results["failed"] += 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_1_mealtime_proximity():
    """Simulate: tourist standing still in Galle at 12:30 local time."""
    _header("1. MEALTIME PROXIMITY — Lunchtime near Galle")

    # Build a timestamp that is 12:30 in Sri Lanka (UTC+5:30)
    local_noon = datetime.now(COLOMBO).replace(hour=12, minute=30, second=0, microsecond=0)
    utc_ts = local_noon.astimezone(timezone.utc)

    ctx = UserContextPayload(
        user_id="test-user-1",
        timestamp=utc_ts,
        location=UserLocation(lat=6.0329, lng=80.2168, city="Galle", district="Galle"),
        activity=UserActivity.STILL,
    )
    triggers = detect_micro_moments(ctx)
    _check("Lunchtime trigger fires at 12:30 in Galle", triggers, MicroMomentType.MEALTIME_PROXIMITY)


def test_2_weather_alert():
    """Simulate: rain forecast slot 20 min from now near Colombo."""
    _header("2. WEATHER ALERT — Rain in 20 min near Colombo")

    now_utc = datetime.now(timezone.utc)
    rain_slot_time = now_utc + timedelta(minutes=20)

    ctx = UserContextPayload(
        user_id="test-user-2",
        timestamp=now_utc,
        location=UserLocation(lat=6.9271, lng=79.8612, city="Colombo", district="Colombo"),
        activity=UserActivity.WALKING,
    )

    env = {
        "weather_forecast": [
            {
                "dt_utc": rain_slot_time.isoformat(),
                "rain_3h_mm": 5.0,
                "condition": "Rain",
                "pop": 0.85,
            }
        ]
    }

    triggers = detect_micro_moments(ctx, env)
    _check("Weather alert fires for rain in ~20 min", triggers, MicroMomentType.WEATHER_ALERT)


def test_3_crowd_surge():
    """Simulate: Sigiriya has crowd index 0.92 — user plans to visit."""
    _header("3. CROWD SURGE — Sigiriya overcrowded")

    ctx = UserContextPayload(
        user_id="test-user-3",
        timestamp=datetime.now(timezone.utc),
        location=UserLocation(lat=7.9570, lng=80.7603, city="Sigiriya", district="Matale"),
        activity=UserActivity.STILL,
        planned_poi_ids=["sigiriya_rock_fortress"],
    )

    env = {
        "crowd_levels": {
            "sigiriya_rock_fortress": {
                "crowd_index": 0.92,
                "crowd_level": "very_high",
                "poi_title": "Sigiriya Rock Fortress",
            }
        }
    }

    triggers = detect_micro_moments(ctx, env)
    _check("Crowd surge fires for Sigiriya at 0.92", triggers, MicroMomentType.CROWD_SURGE)


def test_4_golden_hour():
    """Simulate: sunset in 40 min near Mirissa beach."""
    _header("4. GOLDEN HOUR — Sunset near Mirissa")

    now_utc = datetime.now(timezone.utc)
    sunset_time = now_utc + timedelta(minutes=40)

    ctx = UserContextPayload(
        user_id="test-user-4",
        timestamp=now_utc,
        location=UserLocation(lat=5.9483, lng=80.4589, city="Mirissa", district="Matara"),
        activity=UserActivity.WALKING,
    )

    env = {
        "sunset_utc": sunset_time.isoformat(),
    }

    triggers = detect_micro_moments(ctx, env)
    _check("Golden hour fires for sunset in ~40 min", triggers, MicroMomentType.GOLDEN_HOUR)


def test_5_transit_window():
    """Simulate: user has 90 min gap before next itinerary stop in Kandy."""
    _header("5. TRANSIT WINDOW — 90 min free in Kandy")

    now_utc = datetime.now(timezone.utc)
    next_stop = now_utc + timedelta(minutes=90)

    ctx = UserContextPayload(
        user_id="test-user-5",
        timestamp=now_utc,
        location=UserLocation(lat=7.2906, lng=80.6337, city="Kandy", district="Kandy"),
        activity=UserActivity.STILL,
    )

    env = {
        "next_activity_at": next_stop.isoformat(),
    }

    triggers = detect_micro_moments(ctx, env)
    _check("Transit window fires for 90 min gap", triggers, MicroMomentType.TRANSIT_WINDOW)


def test_6_cultural_event():
    """Simulate: Kandy Esala Perahera happening 3 km away."""
    _header("6. CULTURAL EVENT — Esala Perahera near Kandy")

    now_utc = datetime.now(timezone.utc)

    ctx = UserContextPayload(
        user_id="test-user-6",
        timestamp=now_utc,
        location=UserLocation(lat=7.2906, lng=80.6337, city="Kandy", district="Kandy"),
        activity=UserActivity.WALKING,
    )

    env = {
        "nearby_events": [
            {
                "name": "Kandy Esala Perahera",
                "lat": 7.2945,
                "lng": 80.6410,
                "category": "perahera",
                "start_utc": (now_utc - timedelta(hours=1)).isoformat(),
                "end_utc": (now_utc + timedelta(hours=3)).isoformat(),
            }
        ]
    }

    triggers = detect_micro_moments(ctx, env)
    _check("Cultural event fires for Perahera ~0.8 km away", triggers, MicroMomentType.CULTURAL_EVENT)


# ━━━━━━━━━━━━━━━━━━ negative / edge cases ━━━━━━━━━━━━━━━━━━━━━

def test_negative_no_trigger_at_3am():
    """At 3 AM with no environment data, only golden-hour range might fire."""
    _header("NEGATIVE — 3 AM, no env data, should have few/no triggers")

    local_3am = datetime.now(COLOMBO).replace(hour=3, minute=0, second=0, microsecond=0)
    utc_ts = local_3am.astimezone(timezone.utc)

    ctx = UserContextPayload(
        user_id="test-user-neg",
        timestamp=utc_ts,
        location=UserLocation(lat=6.9271, lng=79.8612, city="Colombo"),
        activity=UserActivity.STILL,
    )
    triggers = detect_micro_moments(ctx, {})
    if len(triggers) == 0:
        print(f"  {PASS} No triggers at 3 AM with empty environment (correct)")
        results["passed"] += 1
    else:
        print(f"  {FAIL} Expected 0 triggers at 3 AM, got {len(triggers)}: {[t.moment_type.value for t in triggers]}")
        results["failed"] += 1


# ━━━━━━━━━━━━━━━━━━━━ LIVE mode (real data) ━━━━━━━━━━━━━━━━━━━

def test_live_real_weather_and_location(lat: float = 6.9271, lng: float = 79.8612):
    """
    LIVE TEST: Uses
      - GPS coordinates (passed via --lat / --lng or default Colombo)
      - Reverse geocoding via OpenWeather API to resolve city name
      - Real OpenWeather weather forecast API
      - Real sunrise/sunset computation
    and runs all 6 detectors against actual environment data.
    """
    _header("LIVE — Real Weather + GPS Coordinates")

    from src.proactive.proactivity_handler import (
        reverse_geocode,
        build_environment,
        _compute_sun_times,
    )

    # 1. Reverse-geocode city from GPS coordinates
    print(f"  📍 GPS coords : ({lat:.4f}, {lng:.4f})")
    print("  🔄 Reverse-geocoding city from coordinates...")
    geo = reverse_geocode(lat, lng)
    city = geo.get("city", "Unknown")
    district = geo.get("district", "")
    print(f"  📍 Location : {city}, {district} ({lat:.4f}, {lng:.4f})")
    print(f"  🌐 Source   : {geo.get('source', 'reverse_geocode')}")

    # 2. Build context
    now_utc = datetime.now(timezone.utc)
    ctx = UserContextPayload(
        user_id="live-test-user",
        timestamp=now_utc,
        location=UserLocation(
            lat=lat, lng=lng, city=city, district=district,
        ),
        activity=UserActivity.STILL,
    )

    # 3. Build REAL environment (weather API + sun times)
    print("\n  🌤️  Fetching real weather from OpenWeather API...")
    env = build_environment(ctx)

    # Show what weather data we got
    slots = env.get("weather_forecast", [])
    print(f"  📊 Weather slots received: {len(slots)}")
    if slots:
        first = slots[0]
        print(f"     First slot: {first.get('dt_utc')} | "
              f"temp={first.get('temp')}°C | "
              f"condition={first.get('weather_main')} | "
              f"pop={first.get('pop')} | "
              f"rain={first.get('rain_3h_mm')} mm")

    sun_rise = env.get("sunrise_utc", "N/A")
    sun_set = env.get("sunset_utc", "N/A")
    print(f"  🌅 Sunrise UTC : {sun_rise}")
    print(f"  🌇 Sunset UTC  : {sun_set}")

    # 4. Run ALL detectors with real data
    triggers = detect_micro_moments(ctx, env)
    print(f"\n  🔍 Detectors ran → {len(triggers)} trigger(s) fired:\n")

    if not triggers:
        print(f"  ℹ️  No triggers fired at this time/location (this is valid)")
        print(f"      Current local time: {now_utc.astimezone(ZoneInfo('Asia/Colombo')).strftime('%H:%M')}")
        print(f"      Try running at meal times (7-9, 11-14, 18-21) or near sunset.")
        results["passed"] += 1
    else:
        for t in triggers:
            print(f"  {PASS} {t.moment_type.value}")
            print(f"       Confidence : {t.confidence:.2f}")
            print(f"       Reason     : {t.reason}")
            print(f"       Metadata   : {json.dumps(t.metadata, default=str)}")
            print()
            results["passed"] += 1


# ━━━━━━━━━━━━━━━━━━━━ runner ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    live_mode = "--live" in sys.argv

    if live_mode:
        # Parse --lat=... and --lng=... from CLI args
        cli_lat, cli_lng = 6.9271, 79.8612  # default: Colombo
        for arg in sys.argv:
            if arg.startswith("--lat="):
                cli_lat = float(arg.split("=", 1)[1])
            elif arg.startswith("--lng="):
                cli_lng = float(arg.split("=", 1)[1])

        print("\n🔴 LIVE Micro-Moment Test (Real Weather + GPS Coordinates)")
        print("=" * 60)
        test_live_real_weather_and_location(lat=cli_lat, lng=cli_lng)
    else:
        print("\n🔍 Micro-Moment Context Trigger Test Suite (Simulated)")
        print("=" * 60)

        test_1_mealtime_proximity()
        test_2_weather_alert()
        test_3_crowd_surge()
        test_4_golden_hour()
        test_5_transit_window()
        test_6_cultural_event()
        test_negative_no_trigger_at_3am()

    print(f"\n{'='*60}")
    total = results["passed"] + results["failed"]
    print(f"  Results: {results['passed']}/{total} passed, {results['failed']} failed")
    print(f"{'='*60}\n")
