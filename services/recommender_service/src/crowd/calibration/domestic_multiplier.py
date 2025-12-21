from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple, Any

import numpy as np
import pandas as pd

from configs.recommender_service.config import CROWD_DOMESTIC_MULTIPLIERS_JSON
from services.recommender_service.src.crowd.data.arrivals_loader import load_sltda_arrivals_monthly


def derive_relative_domestic_multipliers_from_arrivals(
    years: Tuple[int, int] = (2018, 2019),
    min_multiplier: float = 1.00,
    max_multiplier: float = 1.30,
) -> Dict[int, float]:
    """
    Proof-worthy logic (PRIOR):
    - Uses 2018–2019 as pre-COVID baseline.
    - Computes month seasonality index from foreign arrivals distribution.
    - Converts that into a *relative* domestic pressure prior:
        higher foreign-season months -> higher overall crowd pressure overlap expected.
    - Outputs multipliers in a bounded range [min_multiplier, max_multiplier].

    NOTE: This is a PRIOR, not a measured domestic count.
    Replace later if you obtain true domestic mobility/visitation counts by month.
    """

    arrivals = load_sltda_arrivals_monthly().df.copy()
    arrivals["year"] = pd.to_numeric(arrivals["year"], errors="coerce")

    arrivals = arrivals[(arrivals["year"] >= years[0]) & (arrivals["year"] <= years[1])]
    if arrivals.empty:
        raise ValueError(
            f"No arrivals data found in baseline years {years}. "
            f"Check your SLTDA CSV content/years."
        )

    # average arrivals per month (1..12)
    m = arrivals.groupby("month")["arrivals"].mean().reindex(range(1, 13)).fillna(0)

    vals = m.values.astype(float)
    mu = float(vals.mean())
    sd = float(vals.std()) if float(vals.std()) > 1e-9 else 1.0
    z = (vals - mu) / sd

    # scale z into [min,max]
    zmin, zmax = float(z.min()), float(z.max())
    if abs(zmax - zmin) < 1e-9:
        scaled = np.ones_like(z) * min_multiplier
    else:
        scaled = min_multiplier + (z - zmin) * (max_multiplier - min_multiplier) / (zmax - zmin)

    return {i + 1: float(round(scaled[i], 3)) for i in range(12)}


def save_domestic_multipliers_json(out_path: Path = CROWD_DOMESTIC_MULTIPLIERS_JSON) -> Dict[int, float]:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    multipliers = derive_relative_domestic_multipliers_from_arrivals()

    # Save just multipliers (simple)
    out_path.write_text(json.dumps(multipliers, indent=2), encoding="utf-8")
    return multipliers


def save_domestic_multipliers_with_metadata_json(
    out_path: Path = CROWD_DOMESTIC_MULTIPLIERS_JSON,
    years: Tuple[int, int] = (2018, 2019),
    min_multiplier: float = 1.00,
    max_multiplier: float = 1.30,
) -> Dict[str, Any]:
    """
    Optional (recommended for thesis proof):
    Saves multipliers + raw monthly means and config so you can cite derivation.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    arrivals = load_sltda_arrivals_monthly().df.copy()
    arrivals["year"] = pd.to_numeric(arrivals["year"], errors="coerce")
    base = arrivals[(arrivals["year"] >= years[0]) & (arrivals["year"] <= years[1])]
    if base.empty:
        raise ValueError(f"No arrivals data found in baseline years {years}.")

    monthly_means = (
        base.groupby("month")["arrivals"].mean().reindex(range(1, 13)).fillna(0).to_dict()
    )
    multipliers = derive_relative_domestic_multipliers_from_arrivals(
        years=years, min_multiplier=min_multiplier, max_multiplier=max_multiplier
    )

    payload = {
        "baseline_years": list(years),
        "bounds": {"min": min_multiplier, "max": max_multiplier},
        "monthly_mean_foreign_arrivals": {str(k): float(v) for k, v in monthly_means.items()},
        "domestic_multipliers": {str(k): float(v) for k, v in multipliers.items()},
        "note": "Domestic multipliers are derived priors based on foreign-arrivals seasonality (not measured domestic counts).",
    }

    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
