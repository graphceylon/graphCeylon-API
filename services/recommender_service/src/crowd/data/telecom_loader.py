from __future__ import annotations

from pathlib import Path
from typing import Dict
import csv

from configs.recommender_service.config import CROWD_TELECOM_DISTRICT_COUNTS_CSV
from src.crowd.data.district_norm import norm_district


def load_telecom_district_counts(path: Path = CROWD_TELECOM_DISTRICT_COUNTS_CSV) -> Dict[str, float]:
    p = Path(path)
    if not p.exists():
        return {}

    out: Dict[str, float] = {}
    with p.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d_raw = (row.get("district") or "").strip()
            c = row.get("count")
            if not d_raw or c is None:
                continue

            d = norm_district(d_raw)

            try:
                out[d] = float(str(c).replace(",", ""))
            except Exception:
                continue

    return out
