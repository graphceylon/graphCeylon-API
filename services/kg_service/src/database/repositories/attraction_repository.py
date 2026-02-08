"""Repository for attraction-related database operations."""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from neo4j import Driver

from .base import BaseRepository
from ..utils import DatabasePaths

logger = logging.getLogger(__name__)


class AttractionRepository(BaseRepository):
    """Repository for managing attraction data in Neo4j."""
    
    def __init__(self, driver: Driver):
        """Initialize attraction repository."""
        super().__init__(driver)
    
    def load_schema(self) -> Dict[str, Any]:
        """Load attraction schema (constraints and indexes)."""
        return self.load_schema_from_file('init_attractions_schema.cypher')
    
    def load_from_json(self, file_path: str = None) -> Dict[str, Any]:
        """Load attractions from JSON file.
        
        Args:
            file_path: Optional path to JSON file. If not provided, uses default location.
            
        Returns:
            Dictionary with success status and statistics
        """
        try:
            # Use provided path or default
            if file_path is None:
                file_path = str(DatabasePaths.get_data_file('attractions.json'))
            
            logger.info("Loading attractions from JSON...")
            
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Attractions data file not found: {file_path}")
            
            # Load JSON data
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both direct array and object with 'attractions' key
            if isinstance(data, dict) and 'attractions' in data:
                attractions_data = data['attractions']
            elif isinstance(data, list):
                attractions_data = data
            else:
                raise ValueError("Attractions data must be a list or an object with 'attractions' key")
            
            logger.info(f"Found {len(attractions_data)} attractions to import")
            
            # Import each attraction
            imported_count = 0
            skipped_count = 0
            
            for attraction in attractions_data:
                try:
                    # Extract geolocation data
                    geolocation = attraction.get("geolocation", {})
                    coordinates = geolocation.get("coordinates", {})
                    address_info = geolocation.get("address_info", {})
                    admin_areas = address_info.get("administrative_areas", {})
                    geocoding_meta = geolocation.get("geocoding_metadata", {})
                    
                    # Extract google place data
                    google_data = attraction.get("google_place_data", {})
                    
                    # Create or merge attraction
                    cypher = """
                    MERGE (a:Attraction {title: $title})
                    SET a.description = $description,
                        a.imageUrl = $imageUrl,
                        a.scrapedAt = $scrapedAt,
                        
                        // Coordinates
                        a.latitude = $latitude,
                        a.longitude = $longitude,
                        a.coordinateAccuracy = $coordinateAccuracy,
                        
                        // Address Info
                        a.formattedAddress = $formattedAddress,
                        a.country = $country,
                        a.countryCode = $countryCode,
                        a.province = $province,
                        a.district = $district,
                        a.city = $city,
                        a.postalCode = $postalCode,
                        
                        // Geocoding Metadata
                        a.geocodedAt = $geocodedAt,
                        a.geocodingService = $geocodingService,
                        a.geocodingConfidence = $geocodingConfidence,
                        a.googlePlaceId = $googlePlaceId,
                        
                        // Google Place Data
                        a.rating = $rating,
                        a.userRatingsTotal = $userRatingsTotal,
                        a.website = $website,
                        a.phoneNumber = $phoneNumber,
                        a.priceLevel = $priceLevel,
                        a.placeUrl = $placeUrl,
                        a.editorialSummary = $editorialSummary,
                        a.placeName = $placeName,
                        a.vicinity = $vicinity,
                        a.placeTypes = $placeTypes,
                        
                        // Map Links (as JSON strings)
                        a.googleMapsUrl = $googleMapsUrl,
                        a.googleMapsDirectionsUrl = $googleMapsDirectionsUrl,
                        a.googleEarthUrl = $googleEarthUrl,
                        a.coordinatesDMS = $coordinatesDMS,
                        
                        // Links (as JSON string)
                        a.links = $links,
                        
                        a.updatedAt = datetime()
                    WITH a
                    WHERE a.createdAt IS NULL
                    SET a.createdAt = datetime()
                    RETURN a.title AS title
                    """
                    
                    # Extract map links
                    map_links = geolocation.get("map_links", {})
                    
                    params = {
                        "title": attraction.get("title", ""),
                        "description": attraction.get("description", ""),
                        "imageUrl": attraction.get("image_url", ""),
                        "scrapedAt": attraction.get("scraped_at", ""),
                        
                        # Coordinates
                        "latitude": coordinates.get("latitude"),
                        "longitude": coordinates.get("longitude"),
                        "coordinateAccuracy": coordinates.get("accuracy", ""),
                        
                        # Address Info
                        "formattedAddress": address_info.get("formatted_address", ""),
                        "country": admin_areas.get("country", ""),
                        "countryCode": admin_areas.get("country_code", ""),
                        "province": admin_areas.get("province", ""),
                        "district": admin_areas.get("district", ""),
                        "city": admin_areas.get("city", ""),
                        "postalCode": admin_areas.get("postal_code", ""),
                        
                        # Geocoding Metadata
                        "geocodedAt": geocoding_meta.get("geocoded_at", ""),
                        "geocodingService": geocoding_meta.get("geocoding_service", ""),
                        "geocodingConfidence": geocoding_meta.get("geocoding_confidence", ""),
                        "googlePlaceId": geocoding_meta.get("place_id", ""),
                        
                        # Google Place Data
                        "rating": google_data.get("rating"),
                        "userRatingsTotal": google_data.get("user_ratings_total"),
                        "website": google_data.get("website", ""),
                        "phoneNumber": google_data.get("phone_number", ""),
                        "priceLevel": google_data.get("price_level"),
                        "placeUrl": google_data.get("place_url", ""),
                        "editorialSummary": google_data.get("editorial_summary", ""),
                        "placeName": google_data.get("place_name", ""),
                        "vicinity": google_data.get("vicinity", ""),
                        "placeTypes": json.dumps(google_data.get("place_types", [])),
                        
                        # Map Links
                        "googleMapsUrl": map_links.get("google_maps_url", ""),
                        "googleMapsDirectionsUrl": map_links.get("google_maps_directions_url", ""),
                        "googleEarthUrl": map_links.get("google_earth_url", ""),
                        "coordinatesDMS": map_links.get("coordinates_dms", ""),
                        
                        # Links array
                        "links": json.dumps(attraction.get("links", []))
                    }
                    
                    result = self.execute_cypher(cypher, params)
                    
                    if result:
                        imported_count += 1
                        
                        # Link to district from geolocation data if available
                        district = admin_areas.get("district")
                        if district:
                            try:
                                self.link_to_district(attraction.get("title"), district)
                            except Exception as e:
                                logger.warning(f"Failed to link {attraction.get('title')} to district {district}: {e}")
                    
                except Exception as e:
                    logger.warning(f"Failed to import attraction {attraction.get('title', 'unknown')}: {e}")
                    skipped_count += 1
                    continue
            
            logger.info(f"Successfully imported {imported_count} attractions, skipped {skipped_count}")
            
            # Get final statistics
            stats_query = """
            MATCH (a:Attraction)
            OPTIONAL MATCH (a)-[:LOCATED_IN]->(d:District)
            RETURN count(DISTINCT a) AS total_attractions,
                   count(DISTINCT d) AS linked_districts
            """
            stats = self.execute_cypher(stats_query)
            
            return {
                "success": True,
                "message": "Attractions loaded from JSON",
                "attractions_loaded": imported_count,
                "skipped": skipped_count,
                "statistics": stats[0] if stats else {}
            }
            
        except Exception as e:
            logger.error(f"Failed to load attractions from JSON: {e}")
            raise
    
    def cleanup_relationships(self) -> Dict[str, Any]:
        """Remove all attraction relationships to clean up messy graph."""
        try:
            logger.info("Cleaning up attraction relationships...")
            
            # Count before cleanup
            before_query = "MATCH ()-[r:HAS_ATTRACTION]->() RETURN count(r) AS count"
            before = self.execute_cypher(before_query)
            before_count = before[0]["count"] if before else 0
            
            # Delete HAS_ATTRACTION relationships
            delete_query = """
            MATCH ()-[r:HAS_ATTRACTION]->()
            DELETE r
            RETURN count(r) AS deleted
            """
            self.execute_cypher(delete_query)
            
            # Count after cleanup
            after = self.execute_cypher(before_query)
            after_count = after[0]["count"] if after else 0
            
            deleted = before_count - after_count
            logger.info(f"Cleaned up {deleted} HAS_ATTRACTION relationships")
            
            return {
                "success": True,
                "message": "Attraction relationships cleaned up",
                "deleted_count": deleted
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup attraction relationships: {e}")
            raise
    
    def create(self, attraction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new attraction node (alias for create_attraction)."""
        return self.create_attraction(attraction_data)
    
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
            website: $website,
            phoneNumber: $phone_number,
            formattedAddress: $formatted_address,
            priceLevel: $price_level,
            placeTypes: $place_types,
            links: $links,
            createdAt: datetime()
        })
        RETURN id(a) AS node_id, a.title AS title
        """
        
        # Serialize lists to JSON strings
        place_types = attraction_data.get("place_types", [])
        if isinstance(place_types, list):
            place_types = json.dumps(place_types)
            
        links = attraction_data.get("links", [])
        if isinstance(links, list):
            links = json.dumps(links)
        
        result = self.execute_write(cypher, {
            "title": attraction_data.get("title"),
            "description": attraction_data.get("description"),
            "image_url": attraction_data.get("image_url"),
            "latitude": attraction_data.get("latitude"),
            "longitude": attraction_data.get("longitude"),
            "google_place_id": attraction_data.get("google_place_id"),
            "rating": attraction_data.get("rating"),
            "website": attraction_data.get("website"),
            "phone_number": attraction_data.get("phone_number"),
            "formatted_address": attraction_data.get("formatted_address"),
            "price_level": attraction_data.get("price_level"),
            "place_types": place_types,
            "links": links
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
        
        WITH a, d
        MATCH (d)-[:IN_PROVINCE]->(p:Province)
        MERGE (a)-[:IN_PROVINCE]->(p)
        
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
               a.scrapedAt AS scrapedAt,
               a.latitude AS latitude,
               a.longitude AS longitude,
               a.coordinateAccuracy AS coordinateAccuracy,
               a.formattedAddress AS formattedAddress,
               a.country AS country,
               a.province AS province,
               a.district AS district,
               a.city AS city,
               a.postalCode AS postalCode,
               a.googlePlaceId AS googlePlaceId,
               a.geocodingConfidence AS geocodingConfidence,
               a.rating AS rating,
               a.userRatingsTotal AS userRatingsTotal,
               a.website AS website,
               a.phoneNumber AS phoneNumber,
               a.priceLevel AS priceLevel,
               a.placeUrl AS placeUrl,
               a.editorialSummary AS editorialSummary,
               a.placeName AS placeName,
               a.vicinity AS vicinity,
               a.placeTypes AS placeTypes,
               a.googleMapsUrl AS googleMapsUrl,
               a.googleMapsDirectionsUrl AS googleMapsDirectionsUrl,
               a.googleEarthUrl AS googleEarthUrl,
               a.coordinatesDMS AS coordinatesDMS,
               a.links AS links,
               dist.name AS districtNode,
               prov.name AS provinceNode
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
               a.scrapedAt AS scrapedAt,
               a.latitude AS latitude,
               a.longitude AS longitude,
               a.rating AS rating,
               a.website AS website,
               a.phoneNumber AS phoneNumber,
               a.placeUrl AS placeUrl,
               a.formattedAddress AS formattedAddress,
               a.googleMapsUrl AS googleMapsUrl,
               a.links AS links
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
               a.scrapedAt AS scrapedAt,
               a.latitude AS latitude,
               a.longitude AS longitude,
               a.rating AS rating,
               a.website AS website,
               a.phoneNumber AS phoneNumber,
               a.placeUrl AS placeUrl,
               a.formattedAddress AS formattedAddress,
               a.googleMapsUrl AS googleMapsUrl,
               a.links AS links,
               d.name AS district,
               p.name AS province
        ORDER BY a.title
        """
        
        return self.execute_query(cypher, {"province_name": province_name})
