from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from services.recommender_service.src.crowd.inference.crowd_model import forecast_poi_crowd
from services.recommender_service.src.crowd.data.arrivals_resolver import resolve_total_foreign_arrivals_month
from services.recommender_service.src.sustainability.baselines import load_poi_baselines
from services.recommender_service.src.sustainability.risk import normal_from_ci95, prob_exceed_threshold


def _pressure_from_percentiles(x: float, p50: float, p75: float, p90: float) -> float:
    if x <= p50:
        return 0.25
    if x <= p75:
        return 0.55
    if x <= p90:
        return 0.80
    return 0.95



def forecast_poi_sustainability(
    poi_id: str,
    month_start: date,
    total_foreign_arrivals_month: Optional[int] = None,
) -> Dict[str, Any]:
    poi_id = (poi_id or "").strip().lower()

    if total_foreign_arrivals_month is None:
        res = resolve_total_foreign_arrivals_month(month_start)
        total_foreign_arrivals_month = int(res.arrivals)
        arrivals_source = res.source
    else:
        arrivals_source = "override"

    crowd = forecast_poi_crowd(
        poi_id=poi_id,
        month_start=month_start,
        total_foreign_arrivals_month=int(total_foreign_arrivals_month),
    )
    if crowd.get("status") != "ok":
        return crowd

    baselines = load_poi_baselines()
    b = baselines.get(poi_id)
    if not b:
        return {
            "status": "error",
            "message": f"No baseline percentiles found for '{poi_id}'. Run baseline calibration script first.",
            "hint": "python -m services.recommender_service.src.sustainability.run_baseline_build",
        }

    mean_daily = float(crowd["avg_daily_visitors_mean"])
    # pull CI for POI allocation (foreign_to_poi) and convert to daily visitors CI approx
    poi_ci = ((crowd.get("uncertainty") or {}).get("poi_ci95") or {}).get(poi_id)
    # poi_ci is monthly foreign-to-poi; our mean is daily total incl domestic multiplier
    # simplest: scale CI ratio by mean (keeps uncertainty proportional)
    approx_ci_daily = None
    try:
        if poi_ci and poi_ci[0] is not None and poi_ci[1] is not None:
            low, high = float(poi_ci[0]), float(poi_ci[1])
            m_month_foreign = max(1.0, float(crowd.get("foreign_to_poi_mean", 1.0)))
            # ratio CI around foreign monthly
            low_r = max(0.0, low / m_month_foreign)
            high_r = max(0.0, high / m_month_foreign)
            approx_ci_daily = (mean_daily * low_r, mean_daily * high_r)
    except Exception:
        approx_ci_daily = None

    normal = normal_from_ci95(mean_daily, approx_ci_daily)

    threshold = float(b.p90)  # use P90 as overtourism threshold
    p_over = prob_exceed_threshold(normal.mean, normal.sigma, threshold)

    pressure = _pressure_from_percentiles(mean_daily, b.p50, b.p75, b.p90)
    threshold = float(b.p90)


    # final score: 1 is best, 0 is worst
    # risk (probability) dominates; pressure secondary
    score = float(max(0.0, 1.0 - (0.70 * p_over + 0.30 * pressure)))

    if p_over < 0.20:
        risk_level = "Low"
    elif p_over < 0.45:
        risk_level = "Medium"
    elif p_over < 0.70:
        risk_level = "High"
    else:
        risk_level = "Extreme"

    drivers = [
        f"Self-calibrated baseline (P90={threshold:.0f} visitors/day) derived from model history/forecast horizon",
        f"Probabilistic overcrowding risk p(exceed P90)={p_over:.2f} using uncertainty-aware normal approximation",
        f"Pressure score from percentile banding (mean={mean_daily:.0f} vs P50={b.p50:.0f}/P75={b.p75:.0f}/P90={b.p90:.0f})",
    ]

    return {
        "status": "ok",
        "poi_id": poi_id,
        "month_start": month_start.isoformat(),
        "arrivals_source": arrivals_source,
        "crowd": crowd,
        "baseline": {"p50": b.p50, "p75": b.p75, "p90": b.p90, "p95": b.p95, "n": b.n},
        "risk": {
            "threshold_daily": threshold,
            "mean_daily": normal.mean,
            "sigma_daily": normal.sigma,
            "p_overcrowded": p_over,
            "risk_level": risk_level,
        },
        "sustainability_score": round(score, 3),
        "drivers": drivers,
    }
