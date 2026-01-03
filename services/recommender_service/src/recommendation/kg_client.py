# src/recommendation/kg_client.py
from abc import ABC, abstractmethod
from typing import List, Optional
from .attraction_model import Attraction

class KGClient(ABC):
    """
    Abstract interface between your Recommendation Engine and the Tourism KG.
    Right now it will be backed by JSON.
    Later, your teammate can implement a Neo4j version.
    """

    @abstractmethod
    def get_attractions(
        self,
        region: Optional[str] = None,
        city: Optional[str] = None,
        categories: Optional[list[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Attraction]:
        ...
