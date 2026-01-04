from __future__ import annotations
from typing import Any, Dict, List, Tuple

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

def build_objectives(
    cand: Dict[str, Any],
    payload: Dict[str, Any],
) -> Tuple[List[float], Dict[str, float]]:
    """
    Returns:
      - objectives list for NSGA-II (all MINIMIZE)
      - explain dict for debugging / later explanations
    """

    # 1) preference match proxy from KG (already computed)
    # normalize base score into 0..1-ish range using a soft squash
    base = float(cand.get("_score", 0.0))
    match = 1.0 - (1.0 / (1.0 + max(0.0, base)))  # base=0 =>0, base big => ~1

    # 2) dynamic signals (0..1)
    dyn = cand.get("_dynamic") or {}
    crowd = _clamp01(float(dyn.get("crowd_risk_0_1", 0.5)))
    rain  = _clamp01(float(dyn.get("rain_risk_0_1", 0.5)))
    sus   = _clamp01(float(dyn.get("sustainability_0_1", 0.5)))

    # 3) cost (placeholder until you add price model)
    # if you have per-candidate price later, plug here.
    cost = 0.5

    # Convert to minimization objectives
    objectives = [
        -match,        # maximize match
        -sus,          # maximize sustainability
        crowd,         # minimize crowd
        rain,          # minimize rain risk
        cost,          # minimize cost
    ]

    explain = {
        "match_0_1": match,
        "sustainability_0_1": sus,
        "crowd_risk_0_1": crowd,
        "rain_risk_0_1": rain,
        "cost_0_1": cost,
    }
    return objectives, explain
