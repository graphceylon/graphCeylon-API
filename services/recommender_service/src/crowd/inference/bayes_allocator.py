from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional


# ============================================================
# 1) TELECOM CSV LOADER
# ============================================================

def load_telecom_district_counts_csv(path: Path) -> Dict[str, float]:
    """
    Expected CSV header:
      district,count

    Example rows:
      Colombo,4193342
      Galle,2671580

    Returns:
      {"colombo": 4193342.0, "galle": 2671580.0, ...}
    """
    p = Path(path)
    if not p.exists():
        return {}

    out: Dict[str, float] = {}
    with p.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            district = (row.get("district") or "").strip().lower()
            count_raw = row.get("count")
            if not district or count_raw is None:
                continue
            try:
                out[district] = float(str(count_raw).replace(",", "").strip())
            except Exception:
                continue
    return out


def normalize_counts_to_props(counts: Dict[str, float]) -> Dict[str, float]:
    """
    Convert raw counts into proportions that sum to 1.
    If empty or sum=0, returns {}.
    """
    s = sum(v for v in counts.values() if v is not None)
    if s <= 0:
        return {}
    return {k: float(v) / s for k, v in counts.items()}


# ============================================================
# 2) OPTIONAL: "AGE-DECAY" ON TELECOM EVIDENCE (2024 → 2026 etc.)
#    This keeps telecom usable but reduces its influence in future years.
# ============================================================

def decayed_evidence_strength(
    base_strength: float,
    data_year: int,
    target_year: int,
    half_life_years: float = 3.0,
) -> float:
    """
    Exponential half-life decay:
      strength = base_strength * (0.5 ** (delta_years / half_life_years))

    If target_year <= data_year, no decay.
    """
    dy = max(0, target_year - data_year)
    if dy == 0:
        return base_strength
    return float(base_strength) * (0.5 ** (dy / float(half_life_years)))


# ============================================================
# 3) BAYESIAN FUSION (Dirichlet-Multinomial)
# ============================================================

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
      - alpha_prior: survey priors (proportions)
      - evidence_counts: telecom counts OR telecom proportions (either is fine)
      - prior_strength/evidence_strength: pseudo-count weights (validate in sensitivity tests)
    """

    # Normalize prior into proportions
    ps = sum(alpha_prior.values()) if alpha_prior else 0.0
    if ps > 0:
        alpha_prior = {k: max(1e-9, v / ps) for k, v in alpha_prior.items()}

    # Prior pseudo-counts
    prior_counts = {k: alpha_prior.get(k, 1e-3) * prior_strength for k in keys}

    # Evidence proportions -> pseudo-counts
    ev_sum = sum(evidence_counts.values()) if evidence_counts else 0.0
    if ev_sum > 0:
        ev_props = {k: float(v) / ev_sum for k, v in evidence_counts.items()}
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


# ============================================================
# 4) "FULL" WRAPPER: USE TELECOM CSV INSIDE THE ALLOCATOR
# ============================================================

@dataclass(frozen=True)
class TelecomEvidenceConfig:
    telecom_csv_path: Path
    telecom_data_year: int = 2024              # your CSV year
    evidence_strength_base: float = 220.0      # your previous value
    half_life_years: float = 3.0               # decay speed (tuneable)


def allocate_foreign_to_districts_with_telecom(
    total_foreign: int,
    district_keys: List[str],
    region_priors: Dict[str, float],
    telecom_cfg: TelecomEvidenceConfig,
    target_year: int,
    prior_strength_region: float = 60.0,
    n_samples: int = 600,
) -> Tuple[Dict[str, float], Dict[str, Tuple[float, float]], Dict[str, float]]:
    """
    Returns:
      mean_alloc, ci95, debug_info
    debug_info includes:
      - telecom_rows_loaded
      - evidence_strength_used
      - evidence_sum
    """

    # Load telecom evidence from CSV
    telecom_counts_raw = load_telecom_district_counts_csv(telecom_cfg.telecom_csv_path)

    # IMPORTANT: your allocator expects keys to match. We lower-case districts.
    # So we lower-case the district_keys too.
    keys = [k.strip().lower() for k in district_keys]

    # Filter telecom evidence to only known keys (optional but safer)
    telecom_counts = {k: telecom_counts_raw.get(k, 0.0) for k in keys}

    # Decay evidence strength if target year is far in future
    evidence_strength_used = decayed_evidence_strength(
        base_strength=telecom_cfg.evidence_strength_base,
        data_year=telecom_cfg.telecom_data_year,
        target_year=target_year,
        half_life_years=telecom_cfg.half_life_years,
    )

    mean_alloc, ci95 = dirichlet_multinomial_allocate(
        total=total_foreign,
        keys=keys,
        alpha_prior=region_priors,            # survey priors (can be {}) - still works
        evidence_counts=telecom_counts,       # ✅ telecom from CSV
        prior_strength=prior_strength_region,
        evidence_strength=evidence_strength_used,
        n_samples=n_samples,
    )

    debug = {
        "telecom_rows_loaded": float(len([v for v in telecom_counts_raw.values() if v > 0])),
        "evidence_strength_used": float(evidence_strength_used),
        "evidence_sum": float(sum(telecom_counts.values())),
    }
    return mean_alloc, ci95, debug


# ============================================================
# 5) MINIMAL EXAMPLE USAGE
# ============================================================
if __name__ == "__main__":
    # Put your CSV somewhere stable, e.g.:
    #   data/recommender_service/clean/crowd/telecom_district_counts_2024.csv
    telecom_csv = Path("/Users/dev/Desktop/graphCeylon-API/data/recommender_service/clean/crowd/telecom_district_counts_2024.csv")

    cfg = TelecomEvidenceConfig(
        telecom_csv_path=telecom_csv,
        telecom_data_year=2024,
        evidence_strength_base=220.0,
        half_life_years=3.0,
    )

    # Example: allocate 535,000 foreign arrivals (Jan 2026 forecast) into districts
    total_foreign = 535000
    target_year = 2026

    # Your district list should be all districts your system uses (keys must match priors + telecom)
    districts = ["Colombo", "Galle", "Matale", "Kandy", "Gampaha"]

    # Example survey prior (optional). If empty, the telecom dominates (still OK).
    survey_priors = {
        "colombo": 0.20,
        "galle": 0.12,
        "matale": 0.05,
        "kandy": 0.18,
        "gampaha": 0.15,
    }

    mean_alloc, ci95, debug = allocate_foreign_to_districts_with_telecom(
        total_foreign=total_foreign,
        district_keys=districts,
        region_priors=survey_priors,
        telecom_cfg=cfg,
        target_year=target_year,
        prior_strength_region=60.0,
        n_samples=600,
    )

    print("DEBUG:", debug)
    print("MEAN ALLOC:", mean_alloc)
    print("CI95:", ci95)
