from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from configs.recommender_service.config import CROWD_REGION_PRIORS_JSON, CROWD_POI_PRIORS_JSON


def load_region_priors(path: Path = CROWD_REGION_PRIORS_JSON) -> Dict[str, float]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def load_poi_priors(path: Path = CROWD_POI_PRIORS_JSON) -> Dict[str, Dict[str, float]]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))
