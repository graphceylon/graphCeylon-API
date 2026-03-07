# Proactive Micro-Moments — End-to-End Flow

## Step 1 — Flutter Heartbeat

Flutter app runs a 60-second timer. Each tick reads the device GPS and clock, then POSTs to the backend:

```json
{
  "user_id": "device-123",
  "lat": 6.9271,
  "lng": 79.8612,
  "timestamp": "2026-03-07T12:30:00+05:30"
}
```

**Endpoint:** `POST /proactive/context-check`

---

## Step 2 — API Route Parses Request

- `lat`/`lng` → `UserLocation`
- `timestamp` → parsed with timezone
- `city` → left empty (auto-resolved in Step 3)

Calls `handle_context_update(ctx)`.

---

## Step 3 — Build Environment

Four data fetches driven by GPS + timestamp:

| Fetch | Source | What |
|-------|--------|------|
| Reverse geocode | OpenWeather API | GPS → city name ("Colombo") |
| Weather forecast | OpenWeather API | 3-hour rain/temp slots |
| Sunrise/sunset | Solar equations | Computed from lat/lng |
| Hotels (time-gated) | KG service | Only during 05–09, 11–14, 16–21 local hours |

---

## Step 4 — Detect Micro-Moments

Six detectors run against the context + environment:

| Moment | Fires when | Confidence |
|--------|-----------|------------|
| Mealtime | Local hour in 6–9, 11–14, 18–21 | 0.80 |
| Weather Alert | Rain ≥ 1mm forecast within 60 min | 0.60–0.85 |
| Crowd Surge | Planned POI crowd index > 0.75 | 0.70–0.90 |
| Golden Hour | Sunset/sunrise within 60 min | 0.55–0.70 |
| Transit Window | ≥ 30 min gap before next activity | 0.60–0.70 |
| Cultural Event | Event within radius and currently on | 0.60–0.85 |

Returns triggers sorted by confidence (highest first).

---

## Step 5 — Filter Triggers

Each trigger passes through gates (in order):

1. User prefs enabled?
2. Not in quiet hours (22:00–07:00)?
3. Moment type not opted-out?
4. Confidence ≥ user min threshold (0.50)?
5. Rate limit not exceeded (3/hr, 12/day)?
6. Cooldown elapsed?

| Moment | Cooldown |
|--------|----------|
| Mealtime | 60 min |
| Weather | 45 min |
| Crowd | 30 min |
| Golden Hour | 120 min |
| Transit | 60 min |
| Cultural | 120 min |

Triggers that fail any gate → `suppressed_count`.

---

## Step 6 — Resolve POIs

For each allowed trigger, nearby attractions are loaded and filtered by moment type:

- **Mealtime** → restaurants, cafes, food spots
- **Weather** → indoor attractions
- **Crowd** → less-crowded alternatives
- **Golden Hour** → scenic viewpoints, beaches
- **Transit** → quick experiences nearby
- **Cultural** → the event itself

---

## Step 7 — Build & Return Response

```json
{
  "triggers_detected": [
    { "moment_type": "mealtime_proximity", "confidence": 0.80, "reason": "It's lunchtime near Colombo." }
  ],
  "suggestions": [
    {
      "title": "🍽️ Hungry near Colombo?",
      "body": "It's lunchtime and there are 3 great spots within 2.0 km.",
      "recommended_pois": [ ... ]
    }
  ],
  "suppressed_count": 0,
  "nearby_hotels": [
    { "name": "Cinnamon Lakeside Colombo", "star_rating": 5, "price_range_lkr": { "min": 21870, "max": 26730 } }
  ]
}
```

---

## Step 8 — Flutter Handles Response

- **Triggers** → show push notification or in-app alert
- **Suggestions** → display recommended POIs in a card
- **Hotels** → show nearby hotel options
- **No triggers** → do nothing, wait for next heartbeat

---

## Visual Summary

```
Flutter (60s timer)
  │  GPS + Clock
  ▼
POST /context-check
  │
  ▼
build_environment()
  ├── reverse geocode (GPS → city)
  ├── weather (OpenWeather API)
  ├── sunrise/sunset (computed)
  └── hotels (KG, time-gated)
  │
  ▼
detect_micro_moments() — 6 detectors
  │
  ▼
filter_triggers() — cooldowns, rate-limits, quiet hours
  │
  ▼
resolve POIs + build suggestions
  │
  ▼
JSON response → Flutter → show notification / update UI
```
