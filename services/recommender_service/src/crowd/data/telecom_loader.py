from __future__ import annotations

from pathlib import Path
from typing import Dict
import csv

from configs.recommender_service.config import CROWD_TELECOM_DISTRICT_COUNTS_CSV


def load_telecom_district_counts(path: Path = CROWD_TELECOM_DISTRICT_COUNTS_CSV) -> Dict[str, float]:
    """
    Expected CSV:
      district,count
      Colombo,4193342
      Galle,2671580
      ...
    """
    p = Path(path)
    if not p.exists():
        return {}

    out: Dict[str, float] = {}
    with p.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = (row.get("district") or "").strip()
            c = row.get("count")
            if not d or c is None:
                continue
            try:
                out[d] = float(str(c).replace(",", ""))
            except Exception:
                continue
    return out
