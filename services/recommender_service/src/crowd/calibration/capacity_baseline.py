from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, List
import numpy as np
import pandas as pd

from configs.recommender_service.config import CROWD_POI_CAPACITY_JSON
from src.crowd.data.arrivals_loader import load_sltda_arrivals_monthly


def derive_capacity_from_baseline(
    poi_id: str,
    estimated_daily_series: List[float],
    percentile: float = 0.90,
) -> float:
    """
    Capacity is defined as a baseline planning threshold:
    - Use percentile of estimated daily visitors in baseline years (e.g., 2018-2019)
    - This is not an official capacity. It is a reproducible operational threshold.
    """
    if not estimated_daily_series:
        return 0.0
    return float(np.quantile(np.array(estimated_daily_series), percentile))


def save_capacity_json(capacities: Dict[str, float], out_path: Path = CROWD_POI_CAPACITY_JSON) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(capacities, indent=2), encoding="utf-8")
