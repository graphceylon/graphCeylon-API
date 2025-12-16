# src/kg/client_base.py
from typing import List, Optional, Protocol
from .models import Attraction

class AttractionKGClient(Protocol):
    def search_attractions(
        self,
        city: Optional[str] = None,
        region: Optional[str] = None,
        country: Optional[str] = None,
        poi_name: Optional[str] = None,
        tags: Optional[list[str]] = None,
        activity_type: Optional[str] = None,
        budget_level: Optional[str] = None,
    ) -> List[Attraction]:
        ...

    def get_attraction_by_id(self, attraction_id: str) -> Optional[Attraction]:
        ...
