from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, List
import json
from pathlib import Path
import calendar

from configs.recommender_service.config import (
    CROWD_TELECOM_DISTRICT_COUNTS_CSV,
    CROWD_REGION_PRIORS_JSON,
    CROWD_POI_PRIORS_JSON,
    CROWD_DOMESTIC_MULTIPLIERS_JSON,
    CROWD_POI_CAPACITY_JSON,
)

from services.recommender_service.src.crowd.poi_registry import load_pois, pois_by_district
from services.recommender_service.src.crowd.inference.bayes_allocator import dirichlet_multinomial_allocate
from services.recommender_service.src.crowd.data.telecom_loader import load_telecom_district_counts
from services.recommender_service.src.crowd.data.priors_loader import load_region_priors, load_poi_priors


def _days_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def _load_json_if_exists(path: Path) -> Dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def classify_crowd_level(idx: float) -> str:
    if idx < 0.60:
        return "Low"
    if idx < 0.85:
        return "Medium"
    if idx < 1.10:
        return "High"
    return "Extreme"


def forecast_poi_crowd(
    poi_id: str,
    month_start: date,
    total_foreign_arrivals_month: int,
    # optional overrides from API
    telecom_district_counts: Optional[Dict[str, float]] = None,
    region_priors: Optional[Dict[str, float]] = None,
    poi_priors: Optional[Dict[str, Dict[str, float]]] = None,
    # Bayesian strengths (kept explicit in function for sensitivity testing)
    prior_strength_region: float = 60.0,
    prior_strength_poi: float = 50.0,
    evidence_strength_telecom: float = 220.0,
) -> Dict[str, Any]:
    """
    3-source fusion (research-defensible):

    Source A: monthly foreign arrivals (SARIMA or known month value)
    Source B: telecom district distribution (2024) -> evidence for district allocation
    Source C: survey priors (2017/2018/2019) -> priors for region + POI allocation

    Domestic multipliers + capacity are not fixed constants:
    - multipliers are derived priors from arrivals seasonality (unless overridden)
    - capacity is a baseline percentile threshold (if available)
    """

    # ---------- Load supporting data ----------
    pois = load_pois()
    by_dist = pois_by_district(pois)
    target = next((p for p in pois if p.poi_id == poi_id), None)
    if target is None:
        return {"status": "error", "message": f"Unknown poi_id '{poi_id}' (must match KG slug)."}
    if not target.district:
        return {"status": "error", "message": f"POI '{poi_id}' has no district in KG; cannot allocate."}

    target_dist = target.district.strip().lower()
    districts = sorted(list(by_dist.keys()))

    # telecom evidence
    telecom = telecom_district_counts or load_telecom_district_counts(CROWD_TELECOM_DISTRICT_COUNTS_CSV)
    telecom = {k.strip().lower(): float(v) for k, v in telecom.items()} if telecom else {}

    # survey priors
    reg_priors = region_priors or load_region_priors(CROWD_REGION_PRIORS_JSON)  # optional
    poi_pr = poi_priors or load_poi_priors(CROWD_POI_PRIORS_JSON)               # optional

    # derived domestic multipliers (priors) + capacity baseline
    dom_mults = _load_json_if_exists(CROWD_DOMESTIC_MULTIPLIERS_JSON)  # {1:1.12,...}
    dom_mult = float(dom_mults.get(str(month_start.month), dom_mults.get(month_start.month, 1.0))) if dom_mults else 1.0

    capacity_map = _load_json_if_exists(CROWD_POI_CAPACITY_JSON)  # {"sigiriya": 9200}
    capacity = float(capacity_map.get(poi_id, 0.0)) if capacity_map else 0.0

    # ---------- Stage 1: Allocate foreign arrivals to districts (telecom evidence) ----------
    # Prior: uniform unless you provide region priors mapped to districts later
    alpha_prior_district = {d: 1.0 / len(districts) for d in districts}

    district_mean, district_ci = dirichlet_multinomial_allocate(
        total=total_foreign_arrivals_month,
        keys=districts,
        alpha_prior=alpha_prior_district,
        evidence_counts=telecom,
        prior_strength=prior_strength_region,
        evidence_strength=evidence_strength_telecom,
        n_samples=700,
    )

    foreign_in_target_dist = float(district_mean.get(target_dist, 0.0))

    # ---------- Stage 2: Allocate district arrivals to POIs (POI priors from surveys + smoothing) ----------
    pois_in_dist = by_dist.get(target_dist, [])
    poi_keys = [p.poi_id for p in pois_in_dist]

    dist_prior = (poi_pr.get(target_dist, {}) or {})
    # normalize if provided
    s = sum(dist_prior.values())
    if s > 0:
        dist_prior = {k: float(v) / s for k, v in dist_prior.items()}

    base = 1e-3  # smoothing for missing POIs
    alpha_prior_poi = {k: base for k in poi_keys}
    for k, v in dist_prior.items():
        if k in alpha_prior_poi:
            alpha_prior_poi[k] = max(base, float(v))

    poi_mean, poi_ci = dirichlet_multinomial_allocate(
        total=int(round(foreign_in_target_dist)),
        keys=poi_keys,
        alpha_prior=alpha_prior_poi,
        evidence_counts={},  # no POI evidence yet
        prior_strength=prior_strength_poi,
        evidence_strength=0.0,
        n_samples=700,
    )

    foreign_to_poi = float(poi_mean.get(poi_id, 0.0))

    # ---------- Stage 3: Domestic pressure (derived prior) ----------
    # total pressure = foreign_to_poi * domestic_multiplier_prior
    total_monthly = foreign_to_poi * max(1.0, dom_mult)

    # ---------- Stage 4: Crowd index ----------
    days = _days_in_month(month_start)
    avg_daily = total_monthly / days

    # If capacity not available yet, return index relative to self baseline (avoid fake number)
    if capacity <= 0:
        crowd_index = None
        crowd_level = "Unknown"
        capacity_note = "Capacity baseline not calibrated yet (use percentile baseline script)."
    else:
        crowd_index = float(avg_daily / capacity)
        crowd_level = classify_crowd_level(crowd_index)
        capacity_note = "Capacity baseline derived from percentile threshold (not official site capacity)."

    drivers = [
        "Foreign arrivals input (SLTDA monthly / SARIMA forecast)",
        "District allocation calibrated by telecom distribution (Bayesian evidence fusion)",
        "POI allocation driven by survey priors + smoothing (Bayesian prior)",
        "Domestic pressure multiplier derived from arrivals seasonality (prior) unless overridden",
        capacity_note,
    ]

    return {
        "status": "ok",
        "poi_id": poi_id,
        "poi_title": target.title,
        "district": target.district,
        "province": target.province,
        "month_start": month_start.isoformat(),
        "total_foreign_arrivals_month": int(total_foreign_arrivals_month),
        "foreign_in_target_district_mean": round(foreign_in_target_dist),
        "foreign_to_poi_mean": round(foreign_to_poi),
        "domestic_multiplier_used": round(float(dom_mult), 3),
        "estimated_monthly_visitors_mean": round(total_monthly),
        "avg_daily_visitors_mean": round(avg_daily),
        "capacity_per_day": round(capacity) if capacity > 0 else None,
        "crowd_index_mean": round(float(crowd_index), 3) if crowd_index is not None else None,
        "crowd_level": crowd_level,
        "drivers": drivers,
        "uncertainty": {
            "district_ci95": {target_dist: district_ci.get(target_dist)},
            "poi_ci95": {poi_id: poi_ci.get(poi_id)},
            "notes": [
                "Strength parameters are pseudo-count weights; validate via sensitivity testing.",
                "Domestic multiplier is a derived prior unless monthly domestic evidence is available.",
            ],
        },
    }
