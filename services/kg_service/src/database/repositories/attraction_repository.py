"""Repository for attraction-related database operations."""

import logging
from typing import List, Dict, Any, Optional
from neo4j import Driver

from .base import BaseRepository


logger = logging.getLogger(__name__)


class AttractionRepository(BaseRepository):
    """Repository for managing attraction data in Neo4j."""
    
    def __init__(self, driver: Driver):
        """Initialize attraction repository."""
        super().__init__(driver)
    
    def create_attraction(self, attraction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new attraction node.
        
        Args:
            attraction_data: Dictionary with attraction properties
            
        Returns:
            Created attraction information
        """
        logger.info(f"Creating attraction: {attraction_data.get('title')}")
        
        cypher = """
        CREATE (a:Attraction {
            title: $title,
            description: $description,
            imageUrl: $image_url,
            latitude: $latitude,
            longitude: $longitude,
            googlePlaceId: $google_place_id,
            rating: $rating,
            createdAt: datetime()
        })
        RETURN id(a) AS node_id, a.title AS title
        """
        
        result = self.execute_write(cypher, {
            "title": attraction_data.get("title"),
            "description": attraction_data.get("description"),
            "image_url": attraction_data.get("image_url"),
            "latitude": attraction_data.get("latitude"),
            "longitude": attraction_data.get("longitude"),
            "google_place_id": attraction_data.get("google_place_id"),
            "rating": attraction_data.get("rating")
        })
        
        node_id = result[0]["node_id"] if result else None
        
        # Link to district if provided
        if attraction_data.get("district"):
            self.link_to_district(
                attraction_data.get("title"),
                attraction_data.get("district")
            )
        
        return {
            "success": True,
            "node_id": node_id,
            "title": attraction_data.get("title")
        }
    
    def link_to_district(self, attraction_title: str, district_name: str) -> Dict[str, Any]:
        """Link an attraction to a district and province.
        
        Args:
            attraction_title: Title of the attraction
            district_name: Name of the district
            
        Returns:
            Link operation result
        """
        logger.info(f"Linking attraction '{attraction_title}' to district '{district_name}'")
        
        cypher = """
        MATCH (a:Attraction {title: $attraction_title})
        MATCH (d:District {name: $district_name})
        MERGE (a)-[:LOCATED_IN]->(d)
        MERGE (d)-[:HAS_ATTRACTION]->(a)
        
        WITH a, d
        MATCH (d)-[:IN_PROVINCE]->(p:Province)
        MERGE (a)-[:IN_PROVINCE]->(p)
        MERGE (p)-[:HAS_ATTRACTION]->(a)
        
        RETURN a.title AS attraction, d.name AS district, p.name AS province
        """
        
        result = self.execute_write(cypher, {
            "attraction_title": attraction_title,
            "district_name": district_name
        })
        
        return {
            "success": True,
            "result": result[0] if result else None
        }
    
    def query_attractions(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query attractions with various filters.
        
        Args:
            filters: Dictionary with filter criteria
            
        Returns:
            List of matching attractions
        """
        logger.info(f"Querying attractions with filters: {filters}")
        
        # Build dynamic query
        match_clause = "MATCH (a:Attraction)"
        where_clauses = []
        params = {}
        
        # Add district filter
        if filters.get("district"):
            match_clause += "-[:LOCATED_IN]->(d:District {name: $district})"
            params["district"] = filters["district"]
        
        # Add province filter
        if filters.get("province"):
            if not filters.get("district"):
                match_clause += "-[:LOCATED_IN]->(d:District)"
            match_clause += "-[:IN_PROVINCE]->(p:Province {name: $province})"
            params["province"] = filters["province"]
        
        # Add title filter
        if filters.get("title"):
            where_clauses.append("toLower(a.title) CONTAINS toLower($title)")
            params["title"] = filters["title"]
        
        # Add coordinates filter
        if filters.get("has_coordinates") is not None:
            if filters["has_coordinates"]:
                where_clauses.append("a.latitude IS NOT NULL AND a.longitude IS NOT NULL")
            else:
                where_clauses.append("a.latitude IS NULL OR a.longitude IS NULL")
        
        # Build WHERE clause
        where_clause = ""
        if where_clauses:
            where_clause = " WHERE " + " AND ".join(where_clauses)
        
        # Build RETURN clause
        return_clause = """
        OPTIONAL MATCH (a)-[:LOCATED_IN]->(dist:District)
        OPTIONAL MATCH (dist)-[:IN_PROVINCE]->(prov:Province)
        RETURN a.title AS title,
               a.description AS description,
               a.imageUrl AS imageUrl,
               a.latitude AS latitude,
               a.longitude AS longitude,
               a.rating AS rating,
               a.googlePlaceId AS googlePlaceId,
               dist.name AS district,
               prov.name AS province
        ORDER BY a.title
        """
        
        limit = filters.get("limit", 10)
        full_query = f"{match_clause}{where_clause} {return_clause} LIMIT {limit}"
        
        result = self.execute_query(full_query, params)
        logger.info(f"Found {len(result)} attractions")
        
        return result
    
    def get_by_district(self, district_name: str) -> List[Dict[str, Any]]:
        """Get all attractions in a specific district.
        
        Args:
            district_name: Name of the district
            
        Returns:
            List of attractions in the district
        """
        logger.info(f"Getting attractions for district: {district_name}")
        
        cypher = """
        MATCH (d:District {name: $district_name})<-[:LOCATED_IN]-(a:Attraction)
        RETURN a.title AS title,
               a.description AS description,
               a.imageUrl AS imageUrl,
               a.latitude AS latitude,
               a.longitude AS longitude,
               a.rating AS rating,
               a.googlePlaceId AS googlePlaceId
        ORDER BY a.title
        """
        
        return self.execute_query(cypher, {"district_name": district_name})
    
    def get_by_province(self, province_name: str) -> List[Dict[str, Any]]:
        """Get all attractions in a specific province.
        
        Args:
            province_name: Name of the province
            
        Returns:
            List of attractions in the province
        """
        logger.info(f"Getting attractions for province: {province_name}")
        
        cypher = """
        MATCH (p:Province {name: $province_name})<-[:IN_PROVINCE]-(d:District)<-[:LOCATED_IN]-(a:Attraction)
        RETURN a.title AS title,
               a.description AS description,
               a.imageUrl AS imageUrl,
               a.latitude AS latitude,
               a.longitude AS longitude,
               a.rating AS rating,
               a.googlePlaceId AS googlePlaceId,
               d.name AS district,
               p.name AS province
        ORDER BY a.title
        """
        
        return self.execute_query(cypher, {"province_name": province_name})
