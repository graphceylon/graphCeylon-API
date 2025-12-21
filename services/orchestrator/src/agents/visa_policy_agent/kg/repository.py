from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Optional, List

class VisaKGRepository:
    def find_policy(self, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

class JsonVisaKGRepository(VisaKGRepository):
    def __init__(self, json_path: str):
        self.rows: List[Dict[str, Any]] = json.loads(Path(json_path).read_text())

    def find_policy(self, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        nat = filters.get("nationality_country")
        dest = filters.get("destination_country")
        purpose = filters.get("purpose")
        days = filters.get("intended_stay_days")

        for r in self.rows:
            if nat and r.get("nationality_country") != nat:
                continue
            if dest and r.get("destination_country") != dest:
                continue
            if purpose and r.get("purpose") != purpose:
                continue
            if days is not None and r.get("max_stay_days") is not None:
                if int(days) > int(r["max_stay_days"]):
                    continue
            return r
        return None
