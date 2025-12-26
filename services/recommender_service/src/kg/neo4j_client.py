# src/kg/neo4j_client.py
from typing import List, Optional
from neo4j import GraphDatabase

from .client_base import AttractionKGClient
from .models import Attraction

class Neo4jKGClient(AttractionKGClient):
    def __init__(self, uri: str, user: str, password: str):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

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
        # TODO: implement Cypher queries
        raise NotImplementedError

    def get_attraction_by_id(self, attraction_id: str) -> Optional[Attraction]:
        # TODO: implement Cypher query
        raise NotImplementedError
