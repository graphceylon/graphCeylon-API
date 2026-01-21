from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

from math import radians, sin, cos, sqrt, atan2

from .enrich_item import enrich_attraction  # your enrichment function


@dataclass
class EnrichConfig:
    # how strongly dynamic signals affect final rank
    w_sustainability: float = 1.2
    w_crowd_avoid: float = 0.8        # higher = avoid crowds more
    w_rain_avoid: float = 0.6         # higher = avoid rain more


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _iso_day(start_date_str: str, day_offset: int) -> str:
    y, m, d = [int(x) for x in start_date_str.split("-")]
    dt = date(y, m, d) + timedelta(days=day_offset)
    return dt.isoformat()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two (lat, lon) points in km."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1.0 - a))
    return R * c


def _extract_anchor_coords(payload: Dict[str, Any]) -> Tuple[float | None, float | None]:
    """
    Pull anchor coords from payload if available.
    Supported:
      - payload["anchor_coords"] = [lat, lng]
      - payload["destination_coords"] = {"lat":..,"lng":..} or [lat,lng]
      - payload["city_coords"] = ...
    """
    for k in ("anchor_coords", "destination_coords", "city_coords"):
        v = payload.get(k)
        if isinstance(v, (list, tuple)) and len(v) == 2:
            try:
                return float(v[0]), float(v[1])
            except Exception:
                return None, None
        if isinstance(v, dict) and "lat" in v and ("lng" in v or "lon" in v):
            try:
                return float(v["lat"]), float(v.get("lng") or v.get("lon"))
            except Exception:
                return None, None
    return None, None


def enrich_and_rerank_candidates(
    *,
    candidates: List[Dict[str, Any]],
    payload: Dict[str, Any],
    cfg: EnrichConfig = EnrichConfig(),
    day_offset: int = 0,
) -> List[Dict[str, Any]]:
    """
    Takes candidates already returned by query_attractions_from_json() (sorted by _score)
    and:
      1) enforces geo constraints (safety-net) so only destination-appropriate POIs remain
      2) enriches each candidate with crowd/weather/sustainability
      3) computes a final score mixing:
         - KG base rank score (_score)
         - sustainability score (0..1)
         - crowd penalty (0..1)
         - rain penalty (0..1)

    Returns candidates sorted by _final_score desc.
    """

    # --- required inputs ---
    start_date = str(payload.get("start_date") or "").strip()
    if not start_date:
        raise ValueError("payload.start_date required for enrichment reranking")

    explicit_city = str(payload.get("city") or payload.get("destination") or "").strip() or None
    country = str(payload.get("country") or "Sri Lanka").strip() or "Sri Lanka"
    eco_pref = float(payload.get("eco_preference") or 0.5)
    date_str = _iso_day(start_date, day_offset)

    # --- GEO SAFETY-NET (prevents Pinnawela/NuwaraEliya/AdamPeak leaking into Kandy) ---
    # You SHOULD still do geo filtering in the JSON-KG query stage.
    # This is a second guard.
    strict_geo = bool(payload.get("strict_geo", True))
    radius_km = float(payload.get("radius_km") or 80.0)

    anchor_lat, anchor_lng = _extract_anchor_coords(payload)

    if strict_geo and anchor_lat is not None and anchor_lng is not None:
        geo_filtered: List[Dict[str, Any]] = []
        for c in candidates:
            lat = c.get("lat")
            lng = c.get("lng")
            if lat is None or lng is None:
                continue

            d = _haversine_km(anchor_lat, anchor_lng, float(lat), float(lng))
            cc = dict(c)
            cc["_distance_km"] = d  # keep for debugging / later use
            if d <= radius_km:
                geo_filtered.append(cc)

        candidates = geo_filtered
    else:
        # If you don't provide anchor coords, we can't safely filter here.
        # Recommendation: attach payload["anchor_coords"] in the KG query stage.
        pass

    # --- caches (avoid repeated model calls) ---
    # weather is per (city, date)
    weather_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
    # crowd is per (attraction_id, date)
    crowd_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}

    out: List[Dict[str, Any]] = []

    for a in candidates:
        aid = str(a.get("attraction_id") or "").strip()
        if not aid:
            continue

        # ----- Enrichment (crowd/weather/sustainability) -----
        key = (aid, date_str)
        if key in crowd_cache:
            enrich = crowd_cache[key]
        else:
            enrich = enrich_attraction(
                attraction_id=aid,
                date_str=date_str,
                eco_preference=eco_pref,
                country=country,
                explicit_city=explicit_city,
            )
            crowd_cache[key] = enrich

        # Optional: cache weather portion separately (useful later)
        city_used = str(enrich.get("city_used_for_weather") or (explicit_city or "Colombo"))
        wkey = (city_used, date_str)
        if wkey not in weather_cache:
            weather_cache[wkey] = enrich.get("weather") or {}

        # ----- Pull normalized signals -----
        crowd_risk = float((enrich.get("crowd") or {}).get("crowd_risk_0_1", 0.5))
        rain_risk = float((enrich.get("weather") or {}).get("rain_risk_0_1", 0.5))

        sust_obj = enrich.get("sustainability") or {}
        sust_score = sust_obj.get("score")
        if sust_score is None:
            sust_score = sust_obj.get("sustainability_score")
        if sust_score is None:
            sust_score = sust_obj.get("value")
        sust_score = _clamp01(float(sust_score or 0.5))

        # ----- Base KG score -----
        base_score = float(a.get("_score", 0.0))

        # ----- Final composite score -----
        final_score = (
            base_score
            + (cfg.w_sustainability * sust_score)
            + (cfg.w_crowd_avoid * (1.0 - _clamp01(crowd_risk)))
            + (cfg.w_rain_avoid * (1.0 - _clamp01(rain_risk)))
        )

        aa = dict(a)
        aa["_enrichment"] = enrich
        aa["_dynamic"] = {
            "date": date_str,
            "crowd_risk_0_1": _clamp01(crowd_risk),
            "rain_risk_0_1": _clamp01(rain_risk),
            "sustainability_0_1": _clamp01(sust_score),
        }
        aa["_final_score"] = float(final_score)
        out.append(aa)

    out.sort(key=lambda x: float(x.get("_final_score", 0.0)), reverse=True)
    return out
