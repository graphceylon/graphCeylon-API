from dataclasses import dataclass
from typing import Optional

@dataclass
class POI:
    poi_id: str
    title: str
    lat: float
    lng: float
    district: str
    province: str
    description: str
