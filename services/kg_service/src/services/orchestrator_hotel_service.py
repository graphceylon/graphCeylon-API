"""
Orchestrator Hotel Service

Business logic for hotel search functionality used by orchestrator service
"""

from typing import List, Dict, Any
import time
from neo4j import Driver

from models.domain.orchestrator import (
    AccommodationSearchRequest,
    HotelItemResponse,
    OrchestratorSearchResponse
)


class OrchestratorHotelService:
    """Service for handling orchestrator hotel search requests"""
    
    # Currency conversion rate (approximate)
    USD_TO_LKR_RATE = 300.0
    
    def __init__(self, driver: Driver):
        """
        Initialize service with Neo4j driver
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
    
    def search_hotels(self, request: AccommodationSearchRequest) -> OrchestratorSearchResponse:
        """
        Search hotels based on orchestrator request criteria
        
        Filters by:
        - City and country
        - Star rating range
        - Required amenities
        - Budget (max price in LKR)
        
        Args:
            request: AccommodationSearchRequest with search criteria
            
        Returns:
            OrchestratorSearchResponse with matched hotels or error
        """
        start_time = time.time()
        
        try:
            with self.driver.session() as session:
                # Build query and parameters
                cypher_query, params = self._build_query(request)
                
                # Execute query
                result = session.run(cypher_query, **params)
                records = list(result)
                
                # Transform records to response items
                items = self._transform_records_to_items(records)
                
                # Calculate execution time
                query_time_ms = round((time.time() - start_time) * 1000, 2)
                
                # Build trace information
                trace = self._build_trace(request, query_time_ms, len(items))
                
                return OrchestratorSearchResponse(
                    ok=True,
                    count=len(items),
                    items=items,
                    trace=trace
                )
                
        except Exception as e:
            # Error response - only ok, error, details
            return OrchestratorSearchResponse(
                ok=False,
                error="Neo4j query failed",
                details=str(e)
            )
    
    def _build_query(self, request: AccommodationSearchRequest) -> tuple[str, Dict[str, Any]]:
        """
        Build Cypher query and parameters from request
        
        Args:
            request: Search request with filters
            
        Returns:
            Tuple of (cypher_query, parameters)
        """
        params = {"limit": request.limit}
        
        # Start with base query - match hotel with optional geography
        cypher_query = """MATCH (h:Hotel)
        OPTIONAL MATCH (h)-[:LOCATED_IN_DISTRICT]->(d:District)
        OPTIONAL MATCH (h)-[:LOCATED_IN_PROVINCE]->(p:Province)
        """
        
        # Build WHERE clauses for hotel properties
        where_clauses = []
        
        # City filter (matches district or city)
        if request.city:
            where_clauses.append("(toLower(d.name) = toLower($city) OR toLower(h.city) = toLower($city))")
            params["city"] = request.city
        
        # Country filter (for Sri Lanka, verify province exists)
        if request.country and request.country.lower() == "sri lanka":
            where_clauses.append("p IS NOT NULL")
        
        # Star rating filters
        if request.min_star_rating is not None:
            where_clauses.append("h.rating >= $min_rating")
            params["min_rating"] = float(request.min_star_rating)
        
        if request.max_star_rating is not None:
            where_clauses.append("h.rating <= $max_rating")
            params["max_rating"] = float(request.max_star_rating)
        
        # Price filter (convert LKR to USD)
        if request.max_price_lkr is not None:
            max_price_usd = request.max_price_lkr / self.USD_TO_LKR_RATE
            where_clauses.append("h.rate_per_night <= $max_price")
            params["max_price"] = max_price_usd
        
        # Add WHERE clause if we have any filters
        if where_clauses:
            cypher_query += "WHERE " + " AND ".join(where_clauses) + "\n"
        
        # If amenities filter exists, add it after initial WHERE clause
        if request.must_have_amenities:
            cypher_query += """
            WITH h, d, p
            MATCH (h)-[:OFFERS_AMENITY]->(am:Amenity)
            WHERE toLower(am.name) IN $required_amenities
            WITH h, d, p, count(DISTINCT am) as amenity_match_count
            WHERE amenity_match_count = $required_amenity_count
            """
            normalized_amenities = [a.lower() for a in request.must_have_amenities]
            params["required_amenities"] = normalized_amenities
            params["required_amenity_count"] = len(request.must_have_amenities)
        else:
            # Carry forward d and p for later use
            cypher_query += "WITH h, d, p\n"
        
        # Add RETURN clause with all needed data
        cypher_query += """
        OPTIONAL MATCH (h)-[:OFFERS_AMENITY]->(amenity:Amenity)
        
        WITH h, d, p, collect(DISTINCT toLower(amenity.name)) as amenities
        
        RETURN 
            h.hotel_id as hotel_id,
            h.name as name,
            COALESCE(h.city, d.name) as city,
            'Sri Lanka' as country,
            h.rating as star_rating,
            h.rate_per_night as rate_usd,
            amenities,
            COALESCE(h.description, p.name + ', ' + d.name) as address,
            h.latitude as latitude,
            h.longitude as longitude,
            p.name as province,
            d.name as district
        ORDER BY h.rating DESC, h.rate_per_night ASC
        LIMIT $limit
        """
        
        return cypher_query, params
    
    def _transform_records_to_items(self, records: List) -> List[HotelItemResponse]:
        """
        Transform Neo4j records to response items
        
        Args:
            records: List of Neo4j records
            
        Returns:
            List of HotelItemResponse objects
        """
        items = []
        
        for record in records:
            # Calculate price range in LKR (±10% from base rate)
            rate_usd = record["rate_usd"] if record["rate_usd"] else 100.0
            base_price_lkr = rate_usd * self.USD_TO_LKR_RATE
            min_price = base_price_lkr * 0.9
            max_price = base_price_lkr * 1.1
            
            # Convert star rating to integer
            star_rating = None
            if record["star_rating"] is not None:
                star_rating = int(round(record["star_rating"]))
            
            # Build address
            address = self._build_address(
                record["district"],
                record["province"],
                record["address"]
            )
            
            # Build geo coordinates with defaults
            geo = {
                "lat": record["latitude"] if record["latitude"] else 6.9271,
                "lon": record["longitude"] if record["longitude"] else 79.8612
            }
            
            item = HotelItemResponse(
                name=record["name"],
                city=record["city"],
                country="Sri Lanka",
                star_rating=star_rating,
                price_range_lkr={
                    "min": round(min_price, 2),
                    "max": round(max_price, 2)
                },
                amenities=record["amenities"] if record["amenities"] else [],
                address=address,
                geo=geo,
                source="neo4j",
                kg_id=f"Hotel:{record['hotel_id']}"
            )
            items.append(item)
        
        return items
    
    def _build_address(
        self,
        district: str,
        province: str,
        fallback: str
    ) -> str:
        """
        Build address string from district and province
        
        Args:
            district: District name
            province: Province name
            fallback: Fallback address string
            
        Returns:
            Formatted address string
        """
        address_parts = []
        if district:
            address_parts.append(district)
        if province:
            address_parts.append(province)
        
        return ", ".join(address_parts) if address_parts else fallback
    
    def _build_trace(
        self,
        request: AccommodationSearchRequest,
        query_time_ms: float,
        result_count: int
    ) -> Dict[str, Any]:
        """
        Build trace information for response
        
        Args:
            request: Original search request
            query_time_ms: Query execution time in milliseconds
            result_count: Number of results returned
            
        Returns:
            Trace dictionary
        """
        trace = {
            "cypher_ms": query_time_ms,
            "filters_applied": {}
        }
        
        # Add applied filters
        if request.city:
            trace["filters_applied"]["city"] = request.city
        if request.min_star_rating is not None:
            trace["filters_applied"]["min_star_rating"] = request.min_star_rating
        if request.max_star_rating is not None:
            trace["filters_applied"]["max_star_rating"] = request.max_star_rating
        if request.must_have_amenities:
            trace["filters_applied"]["must_have_amenities"] = request.must_have_amenities
        if request.max_price_lkr is not None:
            trace["filters_applied"]["max_price_lkr"] = request.max_price_lkr
        
        # Add original trace if provided
        if request.trace:
            trace.update(request.trace)
        
        # Add reason if no results
        if result_count == 0:
            trace["reason"] = "No matches"
        
        return trace
