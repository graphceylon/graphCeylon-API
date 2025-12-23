from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt
from typing import Optional, Tuple


def _norm_cdf(z: float) -> float:
    # standard normal CDF
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


@dataclass(frozen=True)
class NormalApprox:
    mean: float
    sigma: float


def normal_from_ci95(mean: float, ci95: Optional[Tuple[float, float]]) -> NormalApprox:
    """
    Convert (low, high) 95% interval into a normal approximation.
    If CI missing or degenerate, fall back to small sigma.
    """
    if not ci95 or ci95[0] is None or ci95[1] is None:
        return NormalApprox(mean=mean, sigma=max(1.0, 0.10 * max(1.0, mean)))

    low, high = float(ci95[0]), float(ci95[1])
    width = max(0.0, high - low)
    sigma = width / 3.92  # 2 * 1.96
    sigma = max(1.0, sigma)  # guardrail
    return NormalApprox(mean=mean, sigma=sigma)


def prob_exceed_threshold(mean: float, sigma: float, threshold: float) -> float:
    if sigma <= 0:
        return 1.0 if mean > threshold else 0.0
    z = (threshold - mean) / sigma
    return float(1.0 - _norm_cdf(z))
