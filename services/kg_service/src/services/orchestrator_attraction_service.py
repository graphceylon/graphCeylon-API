"""
Orchestrator Attraction Service

Business logic for attraction search functionality used by orchestrator service
"""

from typing import List, Dict, Any, Optional
from neo4j import Driver
import logging

from models.domain.attraction_orchestrator import (
    AttractionSearchRequest,
    AttractionItem,
    AttractionSearchResponse
)

logger = logging.getLogger(__name__)


class OrchestratorAttractionService:
    """Service for handling orchestrator attraction search requests"""
    
    def __init__(self, driver: Driver):
        """
        Initialize service with Neo4j driver
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
    
    def search_attractions(self, request: AttractionSearchRequest) -> AttractionSearchResponse:
        """
        Search attractions using vector similarity search on descriptions,
        filtered by category if specified.
        
        Args:
            request: AttractionSearchRequest with search criteria
            
        Returns:
            AttractionSearchResponse with attractions or error
        """
        try:
            # Use vector search if poi_category is provided
            if request.poi_category:
                logger.info(f"Using vector search for category: {request.poi_category}")
                attractions_data = self._vector_search_by_category(
                    category=request.poi_category,
                    city=request.city,
                    country=request.country,
                    query=request.query or request.poi_category,
                    limit=10
                )
            else:
                # Fallback to city-based search
                logger.info(f"Using city-based search for: {request.city}")
                city = self._normalize_city_name(request.city)
                attractions_data = self._get_attractions_by_city(
                    city=city,
                    country=request.country,
                    poi_name=request.poi_name,
                    poi_category=None,
                    limit=10
                )
            
            # Map to AttractionItem objects
            items = [self._map_to_item(data) for data in attractions_data]
            
            # Generate summary
            summary = self._generate_summary(items, request.city, request.days)
            
            # If no attractions found, return helpful message
            if not items:
                return AttractionSearchResponse(
                    ok=False,
                    city=request.city,
                    country=request.country,
                    items=[],
                    summary="",
                    error="No attractions found",
                    details=f"No attractions available in {request.city}"
                )
            
            return AttractionSearchResponse(
                ok=True,
                city=request.city,
                country=request.country,
                items=items,
                summary=summary
            )
            
        except Exception as e:
            return AttractionSearchResponse(
                ok=False,
                city=request.city,
                country=request.country,
                items=[],
                summary="",
                error="Attraction search failed",
                details=str(e)
            )
    
    def _normalize_city_name(self, city: str) -> str:
        """
        Normalize city names for better matching
        
        Examples:
        - "colombo" -> "Colombo"
        - "KANDY" -> "Kandy"
        """
        city_lower = city.lower().strip()
        
        # Common city aliases/normalizations
        city_aliases = {
            "colombo": "Colombo",
            "kandy": "Kandy",
            "galle": "Galle",
            "jaffna": "Jaffna",
            "negombo": "Negombo",
            "trincomalee": "Trincomalee",
            "anuradhapura": "Anuradhapura",
            "polonnaruwa": "Polonnaruwa",
            "nuwara eliya": "Nuwara Eliya",
            "ella": "Ella",
            "matara": "Matara",
            "badulla": "Badulla",
            "ratnapura": "Ratnapura",
            "kurunegala": "Kurunegala",
            "dambulla": "Dambulla",
            "sigiriya": "Sigiriya",
            "bentota": "Bentota",
            "hikkaduwa": "Hikkaduwa",
            "mirissa": "Mirissa",
            "arugam bay": "Arugam Bay",
        }
        
        # Check if city matches an alias
        if city_lower in city_aliases:
            return city_aliases[city_lower]
        
        # Otherwise return title-cased version
        return city.title()
    
    def _vector_search_by_category(
        self,
        category: str,
        city: str,
        country: str,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Use vector similarity search on description field, filtered by category and city.
        
        Args:
            category: POI category to search for (e.g., "temple", "museum")
            city: City name for location filtering
            country: Country name
            query: Natural language query or category name
            limit: Maximum number of results
            
        Returns:
            List of attraction data dictionaries with similarity scores
        """
        try:
            from services.embeddings import embedding_service
            from core.config import settings
            
            logger.info(f"Vector search: category={category}, city={city}, query={query}")
            
            # Generate embedding for the query
            query_embedding = embedding_service.generate_embedding(query)
            
            if not query_embedding:
                logger.warning("Failed to generate embedding, falling back to regular search")
                return self._get_attractions_by_city(
                    city=self._normalize_city_name(city),
                    country=country,
                    poi_name=None,
                    poi_category=category,
                    limit=limit
                )
            
            # Normalize city name
            normalized_city = self._normalize_city_name(city)
            
            # Pure vector search on descriptions, filtered only by city
            # The embedding similarity will naturally find attractions matching the category
            cypher = f"""
            CALL db.index.vector.queryNodes('{settings.vector_index_name}', $limit * 3, $embedding)
            YIELD node, score
            WHERE toLower(node.city) = toLower($city)
            RETURN node.title AS title,
                   node.description AS description,
                   node.imageUrl AS imageUrl,
                   node.latitude AS latitude,
                   node.longitude AS longitude,
                   node.formattedAddress AS formattedAddress,
                   node.city AS city,
                   node.district AS district,
                   node.province AS province,
                   node.rating AS rating,
                   node.userRatingsTotal AS userRatingsTotal,
                   node.website AS website,
                   node.phoneNumber AS phoneNumber,
                   node.placeTypes AS placeTypes,
                   node.googleMapsUrl AS googleMapsUrl,
                   node.editorialSummary AS editorialSummary,
                   node.vicinity AS vicinity,
                   score
            ORDER BY score DESC
            LIMIT $limit
            """
            
            with self.driver.session() as session:
                result = session.run(cypher, {
                    "embedding": query_embedding,
                    "city": normalized_city,
                    "limit": limit
                })
                matches = [dict(record) for record in result]
            
            logger.info(f"Vector search found {len(matches)} results")
            return matches
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}, falling back to regular search")
            # Fallback to regular search if vector search fails
            return self._get_attractions_by_city(
                city=self._normalize_city_name(city),
                country=country,
                poi_name=None,
                poi_category=category,
                limit=limit
            )
    
    def _get_attractions_by_city(
        self,
        city: str,
        country: str,
        poi_name: Optional[str] = None,
        poi_category: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get attractions from Neo4j filtered by city
        
        Args:
            city: City name
            country: Country name
            poi_name: Optional specific POI name filter
            poi_category: Optional category filter
            limit: Maximum number of results
            
        Returns:
            List of attraction data dictionaries
        """
        # Build dynamic query
        where_clauses = ["toLower(a.city) = toLower($city)"]
        params = {"city": city, "limit": limit}
        
        # Add POI name filter
        if poi_name:
            where_clauses.append("toLower(a.title) CONTAINS toLower($poi_name)")
            params["poi_name"] = poi_name
        
        # Add category filter (search in placeTypes)
        if poi_category:
            where_clauses.append("toLower(a.placeTypes) CONTAINS toLower($poi_category)")
            params["poi_category"] = poi_category
        
        where_clause = " AND ".join(where_clauses)
        
        cypher = f"""
        MATCH (a:Attraction)
        WHERE {where_clause}
        OPTIONAL MATCH (a)-[:LOCATED_IN]->(d:District)
        RETURN a.title AS title,
               a.description AS description,
               a.imageUrl AS imageUrl,
               a.latitude AS latitude,
               a.longitude AS longitude,
               a.formattedAddress AS formattedAddress,
               a.city AS city,
               a.district AS district,
               a.province AS province,
               a.rating AS rating,
               a.userRatingsTotal AS userRatingsTotal,
               a.website AS website,
               a.phoneNumber AS phoneNumber,
               a.priceLevel AS priceLevel,
               a.placeTypes AS placeTypes,
               a.googleMapsUrl AS googleMapsUrl,
               a.editorialSummary AS editorialSummary,
               a.vicinity AS vicinity,
               d.name AS districtNode
        ORDER BY a.rating DESC, a.userRatingsTotal DESC
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(cypher, params)
            return [dict(record) for record in result]
    
    def _map_to_item(self, data: Dict[str, Any]) -> AttractionItem:
        """
        Map Neo4j data to AttractionItem model
        
        Args:
            data: Attraction data from Neo4j
            
        Returns:
            AttractionItem object
        """
        # Extract category from placeTypes
        category = self._extract_category(data.get("placeTypes"))
        
        # Build location string
        location = self._build_location_string(
            data.get("vicinity"),
            data.get("formattedAddress"),
            data.get("city"),
            data.get("district")
        )
        
        # Extract opening hours (from editorialSummary or set as unknown)
        open_hours = self._extract_opening_hours(data.get("editorialSummary"))
        
        # Estimate entry fee from price level
        entry_fee = self._estimate_entry_fee(data.get("priceLevel"))
        
        # Format coordinates
        coordinates = None
        if data.get("latitude") and data.get("longitude"):
            coordinates = f"{data['latitude']}, {data['longitude']}"
        
        return AttractionItem(
            name=data.get("title", "Unknown Attraction"),
            category=category,
            description=data.get("description") or data.get("editorialSummary"),
            location=location,
            open_hours=open_hours,
            entry_fee_lkr=entry_fee,
            source="kg_service",
            rating=data.get("rating"),
            coordinates=coordinates,
            website=data.get("website"),
            phone=data.get("phoneNumber")
        )
    
    def _extract_category(self, place_types: Optional[str]) -> Optional[str]:
        """
        Extract primary category from place types string
        
        Args:
            place_types: Comma-separated place types from Google
            
        Returns:
            Primary category or None
        """
        if not place_types:
            return None
        
        # Common tourist attraction categories
        category_keywords = {
            "temple": "temple",
            "church": "religious site",
            "mosque": "religious site",
            "museum": "museum",
            "park": "park",
            "garden": "garden",
            "zoo": "zoo",
            "beach": "beach",
            "historical": "historical site",
            "monument": "monument",
            "palace": "palace",
            "fort": "fort",
            "waterfall": "natural attraction",
            "lake": "natural attraction",
            "mountain": "natural attraction",
            "viewpoint": "viewpoint",
            "market": "market",
            "shopping": "shopping",
            "restaurant": "dining",
            "hotel": "accommodation"
        }
        
        place_types_lower = place_types.lower()
        for keyword, category in category_keywords.items():
            if keyword in place_types_lower:
                return category
        
        return "attraction"
    
    def _build_location_string(
        self,
        vicinity: Optional[str],
        formatted_address: Optional[str],
        city: Optional[str],
        district: Optional[str]
    ) -> Optional[str]:
        """Build location string from available data"""
        if vicinity:
            return vicinity
        if formatted_address:
            return formatted_address
        if city and district:
            return f"{city}, {district}"
        if city:
            return city
        return None
    
    def _extract_opening_hours(self, editorial_summary: Optional[str]) -> Optional[str]:
        """
        Extract opening hours from editorial summary or other text
        
        Args:
            editorial_summary: Google editorial summary text
            
        Returns:
            Opening hours string or None
        """
        # For now, return generic message
        # TODO: Parse from editorial_summary or add opening_hours field to data
        return "Hours vary, please check website"
    
    def _estimate_entry_fee(self, price_level: Optional[int]) -> Optional[str]:
        """
        Estimate entry fee from Google price level (0-4)
        
        Args:
            price_level: Google price level
            
        Returns:
            Estimated fee string or None
        """
        if price_level is None:
            return "Contact for pricing"
        
        # Map price level to fee ranges (LKR)
        fee_estimates = {
            0: "Free",
            1: "500-1000",
            2: "1000-2000",
            3: "2000-4000",
            4: "4000+"
        }
        
        return fee_estimates.get(price_level, "Contact for pricing")
    
    def _generate_summary(
        self,
        items: List[AttractionItem],
        city: str,
        days: Optional[int] = None
    ) -> str:
        """
        Generate natural language summary of search results
        
        Args:
            items: List of attraction items
            city: City name
            days: Optional trip duration
            
        Returns:
            Summary string
        """
        if not items:
            return f"No attractions found in {city}."
        
        count = len(items)
        
        # Count categories
        categories = {}
        for item in items:
            category = item.category or "attraction"
            categories[category] = categories.get(category, 0) + 1
        
        # Build category summary
        category_parts = []
        for category, cat_count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]:
            category_parts.append(f"{cat_count} {category}{'s' if cat_count > 1 else ''}")
        
        category_text = ", ".join(category_parts)
        
        # Build summary
        summary = f"Found {count} attraction{'s' if count != 1 else ''} in {city}"
        if category_text:
            summary += f" including {category_text}"
        
        # Add trip planning context
        if days:
            if days == 1:
                summary += ". Perfect for a day trip."
            elif days <= 3:
                summary += f". Enough variety for a {days}-day visit."
            else:
                summary += f". Great selection for a {days}-day exploration."
        
        return summary + "."
