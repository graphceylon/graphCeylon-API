# services/recommender_service/src/sustainability/district_crowd/sustainability_score.py

from __future__ import annotations

from typing import Dict, Any, Optional


def _clamp01(x: float) -> float:
    x = float(x)
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def crowd_level_to_0_1(crowd_level: Optional[str]) -> float:
    """
    Converts your discrete crowd labels into a stable 0..1 risk.

    This is the key fix for "same sustainability score everywhere":
    different districts produce different crowd_level => different risk.

    Labels expected from predict_district_crowd():
      Low, Moderate, High, VeryHigh, Extreme
    """
    level = (crowd_level or "").strip().lower()

    mapping = {
        "low": 0.2,
        "moderate": 0.4,
        "medium": 0.4,      # allow alt wording
        "high": 0.6,
        "veryhigh": 0.8,
        "very_high": 0.8,
        "extreme": 1.0,
    }
    return float(mapping.get(level, 0.5))  # unknown -> neutral default


def rain_risk_to_0_1(rain_risk: Optional[str]) -> float:
    """
    Converts weather rain risk into a 0..1 risk.
    Expected from weather service: Low/Medium/High (or None)
    """
    r = (rain_risk or "").strip().lower()
    mapping = {
        "low": 0.2,
        "moderate": 0.5,
        "medium": 0.5,
        "high": 0.8,
        "extreme": 1.0,  # if you ever add it
    }
    return float(mapping.get(r, 0.5))


def compute_sustainability_score(
    *,
    # You can provide crowd_risk directly OR provide crowd_level
    crowd_risk_0_1: Optional[float] = None,
    crowd_level: Optional[str] = None,

    # You can provide rain_risk directly OR provide rain_risk label
    rain_risk_0_1: Optional[float] = None,
    rain_risk: Optional[str] = None,

    eco_preference: float = 0.5,
) -> Dict[str, Any]:
    """
    Higher is better (0..1).

    eco_preference: 0..1 (higher means user cares more about sustainability,
    so crowd penalty becomes more important than rain penalty).

    Weighting:
      w_crowd = 0.3 .. 1.0 (increases with eco_preference)
      w_rain  = 1 - w_crowd
    """

    eco_preference = _clamp01(eco_preference)

    # Resolve crowd risk
    if crowd_risk_0_1 is None:
        crowd_risk_0_1 = crowd_level_to_0_1(crowd_level)
    crowd_risk_0_1 = _clamp01(float(crowd_risk_0_1))

    # Resolve rain risk
    if rain_risk_0_1 is None:
        rain_risk_0_1 = rain_risk_to_0_1(rain_risk)
    rain_risk_0_1 = _clamp01(float(rain_risk_0_1))

    # Weights: crowd is usually bigger factor in sustainability/capacity
    # eco_preference pushes crowd weight higher.
    w_crowd = 0.7 * eco_preference + 0.3   # eco=0 => 0.3, eco=1 => 1.0
    w_rain = 1.0 - w_crowd

    penalty = (w_crowd * crowd_risk_0_1) + (w_rain * rain_risk_0_1)
    score = 1.0 - penalty
    score = _clamp01(score)

    # Nice round for API
    score = round(score, 3)

    if score >= 0.70:
        label = "Good"
    elif score >= 0.40:
        label = "Moderate"
    else:
        label = "Poor"

    return {
        "score_0_1": score,
        "label": label,
        "inputs": {
            "eco_preference": eco_preference,
            "crowd_risk_0_1": crowd_risk_0_1,
            "rain_risk_0_1": rain_risk_0_1,
            "crowd_level": crowd_level,
            "rain_risk": rain_risk,
        },
        "weights": {
            "w_crowd": round(w_crowd, 3),
            "w_rain": round(w_rain, 3),
        },
        "debug": {
            "penalty": round(penalty, 3),
        },
    }
