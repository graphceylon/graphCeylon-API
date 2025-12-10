# src/recommendation/attraction_model.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Attraction:
    id: str
    name: str
    district: str
    province: str 
    city: str
    lat: float
    lon: float

    categories: List[str]        # ["nature"], ["culture"], ["shopping"]
    tags: List[str]              # ["lake", "temple", "heritage"]

    base_price_lkr: float
    avg_visit_hours: float

    eco_sensitivity: float       # 0–1
    capacity_score: float        # 0–1
    popularity_score: float      # 0–1

    image_url: Optional[str] = None
    map_url: Optional[str] = None
