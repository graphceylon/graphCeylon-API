from __future__ import annotations

import random
from typing import Dict, List, Tuple


def _dirichlet_sample(alpha: List[float]) -> List[float]:
    gammas = [random.gammavariate(a, 1.0) if a > 0 else 0.0 for a in alpha]
    s = sum(gammas)
    if s <= 0:
        n = len(alpha)
        return [1.0 / n] * n
    return [g / s for g in gammas]


def _multinomial_draw(n: int, probs: List[float]) -> List[int]:
    counts = [0] * len(probs)
    for _ in range(n):
        r = random.random()
        cum = 0.0
        for i, p in enumerate(probs):
            cum += p
            if r <= cum:
                counts[i] += 1
                break
    return counts


def dirichlet_multinomial_allocate(
    total: int,
    keys: List[str],
    alpha_prior: Dict[str, float],
    evidence_counts: Dict[str, float],
    prior_strength: float,
    evidence_strength: float,
    n_samples: int = 600,
) -> Tuple[Dict[str, float], Dict[str, Tuple[float, float]]]:
    """
    Research-defensible Bayesian fusion:

    - alpha_prior encodes survey priors (older, smaller strength)
    - evidence_counts encodes telecom distribution (strong evidence, larger strength)
    - strengths are pseudo-count sample sizes (not "magic"), and should be validated via sensitivity tests.
    """

    # Normalize prior into proportions if needed
    ps = sum(alpha_prior.values()) if alpha_prior else 0.0
    if ps > 0:
        alpha_prior = {k: max(1e-9, v / ps) for k, v in alpha_prior.items()}

    # Prior pseudo-counts
    prior_counts = {k: alpha_prior.get(k, 1e-3) * prior_strength for k in keys}

    # Evidence proportions -> pseudo-counts
    ev_sum = sum(evidence_counts.values()) if evidence_counts else 0.0
    if ev_sum > 0:
        ev_props = {k: v / ev_sum for k, v in evidence_counts.items()}
        ev_counts = {k: max(1e-9, ev_props.get(k, 0.0)) * evidence_strength for k in keys}
    else:
        ev_counts = {k: 0.0 for k in keys}

    alpha = [prior_counts[k] + ev_counts[k] + 1e-6 for k in keys]

    samples = {k: [] for k in keys}
    for _ in range(n_samples):
        probs = _dirichlet_sample(alpha)
        alloc = _multinomial_draw(total, probs)
        for k, c in zip(keys, alloc):
            samples[k].append(c)

    mean_alloc = {k: sum(samples[k]) / n_samples for k in keys}

    def ci95(vals: List[float]) -> Tuple[float, float]:
        s = sorted(vals)
        lo = s[int(0.025 * (len(s) - 1))]
        hi = s[int(0.975 * (len(s) - 1))]
        return float(lo), float(hi)

    ci = {k: ci95(samples[k]) for k in keys}
    return mean_alloc, ci
