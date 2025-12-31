from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple, Union

import math

# Your existing crowd predictor (the pressure-based one)
from src.sustainability.district_crowd.predict import predict_attraction_crowd
from src.weather.logic import forecast_weather_logic





DateLike = Union[str, datetime, date]


# -----------------------------
# Helpers
# -----------------------------
def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def midpoint_date(start_date: str, end_date: str) -> str:
    s = datetime.fromisoformat(start_date).date()
    e = datetime.fromisoformat(end_date).date()
    mid = s + (e - s) // 2
    return mid.isoformat()


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def rain_label_to_risk_0_1(label: Optional[str]) -> float:
    """
    Your weather outputs use: Low/Medium/High.
    Convert to scalar for ranking.
    """
    if not label:
        return 0.5
    l = str(label).strip().lower()
    if l == "low":
        return 0.2
    if l == "medium":
        return 0.5
    if l == "high":
        return 0.8
    return 0.5


def normalize_weather_payload_to_rain_risk(fc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accepts your exact weather response shape:
      - source: short_range_api_daily OR long_range_models_monthly
      - daily: [{ds, rain_risk, mean_mm, ...}]
      - monthly: [{ds, rain_risk, mean_mm, ...}]  (or internal month mapping via router)

    Returns:
      {
        "mode": "daily"|"monthly"|"unknown",
        "source": "...",
        "rain_risk_0_1": float,
        "rain_risk_label": "Low|Medium|High|Unknown",
        "mean_mm": float|None,
        "raw": fc
      }
    """
    source = str(fc.get("source") or "unknown")

    # daily mode
    daily = fc.get("daily") or []
    if isinstance(daily, list) and len(daily) > 0:
        risks = [rain_label_to_risk_0_1(d.get("rain_risk")) for d in daily if isinstance(d, dict)]
        mm = [d.get("mean_mm") for d in daily if isinstance(d, dict) and d.get("mean_mm") is not None]
        rain_risk_0_1 = float(sum(risks) / max(1, len(risks)))
        # pick "worst" label for explainability (High > Medium > Low)
        labels = [str(d.get("rain_risk")) for d in daily if isinstance(d, dict) and d.get("rain_risk")]
        label_rank = {"low": 0, "medium": 1, "high": 2}
        worst = "Unknown"
        if labels:
            worst = max(labels, key=lambda x: label_rank.get(str(x).lower(), -1))
        return {
            "mode": "daily",
            "source": source,
            "rain_risk_0_1": round(rain_risk_0_1, 4),
            "rain_risk_label": worst,
            "mean_mm": round(float(sum(mm) / len(mm)), 2) if mm else None,
            "raw": fc,
        }

    # monthly mode
    monthly = fc.get("monthly") or []
    if isinstance(monthly, list) and len(monthly) > 0:
        risks = [rain_label_to_risk_0_1(m.get("rain_risk")) for m in monthly if isinstance(m, dict)]
        mm = [m.get("mean_mm") for m in monthly if isinstance(m, dict) and m.get("mean_mm") is not None]
        rain_risk_0_1 = float(sum(risks) / max(1, len(risks)))
        labels = [str(m.get("rain_risk")) for m in monthly if isinstance(m, dict) and m.get("rain_risk")]
        label_rank = {"low": 0, "medium": 1, "high": 2}
        worst = "Unknown"
        if labels:
            worst = max(labels, key=lambda x: label_rank.get(str(x).lower(), -1))
        return {
            "mode": "monthly",
            "source": source,
            "rain_risk_0_1": round(rain_risk_0_1, 4),
            "rain_risk_label": worst,
            "mean_mm": round(float(sum(mm) / len(mm)), 2) if mm else None,
            "raw": fc,
        }

    return {
        "mode": "unknown",
        "source": source,
        "rain_risk_0_1": 0.5,
        "rain_risk_label": "Unknown",
        "mean_mm": None,
        "raw": fc,
    }


def compute_sustainability_score(
    crowd_risk_0_1: float,
    rain_risk_0_1: float,
    eco_preference: float,
) -> Dict[str, Any]:
    """
    MVP sustainability index: higher is better.
    Uses eco_preference as a *weight amplifier* (defensible + preference-aware).
    """
    eco = clamp(float(eco_preference or 0.0))
    penalty = 0.65 * clamp(crowd_risk_0_1) + 0.35 * clamp(rain_risk_0_1)
    score = 1.0 - clamp(penalty * (0.6 + 0.4 * eco))

    if score >= 0.8:
        label = "Excellent"
    elif score >= 0.6:
        label = "Good"
    elif score >= 0.4:
        label = "Fair"
    else:
        label = "Poor"

    return {"score_0_1": round(score, 4), "label": label}


# -----------------------------
# Main enrichment + ranking
# -----------------------------
def enrich_candidates(
    candidates: List[Any],  # List[POI] dataclass objects
    anchor_lat: float,
    anchor_lng: float,
    start_date: str,
    end_date: str,
    final_prefs: Dict[str, Any],
    city: str,
    country: str = "Sri Lanka",
) -> List[Dict[str, Any]]:
    rep_date = midpoint_date(start_date, end_date)
    eco_pref = float(final_prefs.get("eco_preference") or 0.0)

    enriched: List[Dict[str, Any]] = []
    weather_fc = forecast_weather_logic({
            "city": city,             # IMPORTANT: your weather system is city-based; keep consistent with itinerary base
            "country": country,
            "start_date": start_date,
            "end_date": end_date,
            "time_of_day": None,
        })
    weather_norm = normalize_weather_payload_to_rain_risk(weather_fc)
    for poi in candidates:
        # POI is your dataclass -> convert to dict
        p = asdict(poi) if is_dataclass(poi) else dict(poi)

        lat = float(p["lat"])
        lng = float(p["lng"])
        dist = haversine_km(anchor_lat, anchor_lng, lat, lng)

        # ---- Crowd (your new logic) ----
        crowd = predict_attraction_crowd(p["poi_id"], rep_date)
        crowd_risk = float(crowd.get("crowd_risk_0_1") or 0.5)
        crowd_level = crowd.get("crowd_level") or "Unknown"

        # ---- Weather (your existing adaptive logic) ----
        

        # ---- Sustainability ----
        sus = compute_sustainability_score(
            crowd_risk_0_1=crowd_risk,
            rain_risk_0_1=float(weather_norm["rain_risk_0_1"]),
            eco_preference=eco_pref,
        )

        enriched.append({
            **p,
            "context": {
                "rep_date": rep_date,
                "distance_km": round(dist, 2),
                "crowd": {
                    "risk_0_1": round(clamp(crowd_risk), 4),
                    "level": crowd_level,
                    "pressure": crowd.get("total_district_pressure"),
                    "pressure_vs_p90": crowd.get("pressure_vs_p90"),
                    "district": crowd.get("district"),
                    "month_start": crowd.get("month_start"),
                },
                "weather": {
                    "mode": weather_norm["mode"],
                    "source": weather_norm["source"],
                    "rain_risk_0_1": weather_norm["rain_risk_0_1"],
                    "rain_risk_label": weather_norm["rain_risk_label"],
                    "mean_mm": weather_norm["mean_mm"],
                    "raw": weather_norm["raw"],  # keep for explainability/debug
                },
                "sustainability": sus,
            }
        })

    return enriched


def rank_enriched(
    enriched: List[Dict[str, Any]],
    final_prefs: Dict[str, Any],
) -> List[Dict[str, Any]]:
    avoid_crowds = bool(final_prefs.get("avoid_crowds") or False)
    eco_pref = float(final_prefs.get("eco_preference") or 0.0)

    # ---- rule 1: avoid crowds => lowest crowd risk FIRST ----
    if avoid_crowds:
        return sorted(
            enriched,
            key=lambda p: (
                float(p["context"]["crowd"]["risk_0_1"]),
                float(p["context"]["weather"]["rain_risk_0_1"]),
                -float(p["context"]["sustainability"]["score_0_1"]),
                float(p["context"]["distance_km"]),
            )
        )

    # ---- rule 2: strong eco => highest sustainability FIRST ----
    if eco_pref >= 0.7:
        return sorted(
            enriched,
            key=lambda p: (
                -float(p["context"]["sustainability"]["score_0_1"]),
                float(p["context"]["crowd"]["risk_0_1"]),
                float(p["context"]["weather"]["rain_risk_0_1"]),
                float(p["context"]["distance_km"]),
            )
        )

    # ---- default: blended score ----
    def score(p: Dict[str, Any]) -> float:
        crowd = float(p["context"]["crowd"]["risk_0_1"])
        rain = float(p["context"]["weather"]["rain_risk_0_1"])
        sus = float(p["context"]["sustainability"]["score_0_1"])
        dist = float(p["context"]["distance_km"])

        dist_pen = clamp(dist / 80.0)  # typical radius

        # Higher is better
        return (
            0.40 * sus +
            0.30 * (1.0 - crowd) +
            0.20 * (1.0 - rain) +
            0.10 * (1.0 - dist_pen)
        )

    ranked = sorted(enriched, key=score, reverse=True)
    for p in ranked:
        p["context"]["rank_score_0_1"] = round(score(p), 4)
    return ranked


def enrich_and_rank(
    candidates: List[Any],
    anchor_lat: float,
    anchor_lng: float,
    start_date: str,
    end_date: str,
    final_prefs: Dict[str, Any],
    city: str,
    country: str = "Sri Lanka",
) -> List[Dict[str, Any]]:
    enriched = enrich_candidates(
        candidates=candidates,
        anchor_lat=anchor_lat,
        anchor_lng=anchor_lng,
        start_date=start_date,
        end_date=end_date,
        final_prefs=final_prefs,
        city=city,
        country=country,
    )
    return rank_enriched(enriched, final_prefs)
