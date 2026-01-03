# src/kg/models.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Attraction:
    id: str
    name: str
    description: str

    country: str
    province: str
    district: str
    city: str

    latitude: float
    longitude: float

    image_url: Optional[str] = None
    price_level: Optional[str] = None
    place_types: List[str] = None
    tags: List[str] = None
    google_place_id: Optional[str] = None
