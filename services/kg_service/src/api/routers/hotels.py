"""
Hotel API Router

RESTful endpoints for hotel queries, search, recommendations, and ingestion
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File
from pydantic import BaseModel, Field
import json
import time
from datetime import datetime

from neo4j import GraphDatabase
from neo4j.time import DateTime, Date, Time
from core.config import settings
from models.domain.hotel import (
    HotelResponse,
    HotelSearchQuery,
    HotelRecommendationQuery,
    HotelStatistics,
    HotelIngestionResult,
    PriceTier,
    ProximityLevel
)
from services.hotel_ingestion_service import HotelIngestionService
from services.orchestrator_hotel_service import OrchestratorHotelService
from models.domain.orchestrator import (
    AccommodationSearchRequest,
    HotelItemResponse,
    OrchestratorSearchResponse
)


router = APIRouter(
    prefix="/hotels",
    tags=["hotels"],
    responses={404: {"description": "Not found"}}
)


# ========== Helper Functions ==========

def sanitize_neo4j_types(obj: Any) -> Any:
    """Convert Neo4j types to Python native types for JSON serialization"""
    if isinstance(obj, (DateTime, Date, Time)):
        return obj.iso_format()
    elif isinstance(obj, dict):
        return {k: sanitize_neo4j_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_neo4j_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_neo4j_types(item) for item in obj)
    else:
        return obj


# ========== Database Connection ==========

def get_neo4j_driver():
    """Get Neo4j driver instance"""
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    try:
        yield driver
    finally:
        driver.close()


# ========== Response Models ==========

class HotelListResponse(BaseModel):
    """Paginated hotel list response"""
    total: int
    limit: int
    offset: int
    hotels: List[Dict[str, Any]]


class HotelDetailResponse(BaseModel):
    """Detailed hotel response with relationships"""
    hotel: Dict[str, Any]
    nearby_attractions: List[Dict[str, Any]]
    nearby_pois: List[Dict[str, Any]]
    amenities: List[str]


class RecommendationResponse(BaseModel):
    """Hotel recommendation response"""
    query: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    total_cost: float
    optimization_score: float


# ========== Endpoints ==========

@router.get("/", response_model=HotelListResponse)
async def list_hotels(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    province: Optional[str] = None,
    district: Optional[str] = None,
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    max_price: Optional[float] = Query(None, ge=0),
    driver = Depends(get_neo4j_driver)
):
    """
    List all hotels with optional filters
    
    - **limit**: Number of results (max 100)
    - **offset**: Pagination offset
    - **province**: Filter by province
    - **district**: Filter by district
    - **min_rating**: Minimum hotel rating
    - **max_price**: Maximum price per night
    """
    with driver.session() as session:
        # Build query
        where_clauses = []
        params = {"limit": limit, "offset": offset}
        
        if province:
            where_clauses.append("p.name = $province")
            params["province"] = province
        
        if district:
            where_clauses.append("d.name = $district")
            params["district"] = district
        
        if min_rating is not None:
            where_clauses.append("h.rating >= $min_rating")
            params["min_rating"] = min_rating
        
        if max_price is not None:
            where_clauses.append("h.rate_per_night <= $max_price")
            params["max_price"] = max_price
        
        where_clause = " AND " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Count query
        count_query = f"""
        MATCH (h:Hotel)
        OPTIONAL MATCH (h)-[:LOCATED_IN_PROVINCE]->(p:Province)
        OPTIONAL MATCH (h)-[:LOCATED_IN_DISTRICT]->(d:District)
        WHERE 1=1 {where_clause}
        RETURN count(h) as total
        """
        
        total = session.run(count_query, **params).single()["total"]
        
        # Data query
        query = f"""
        MATCH (h:Hotel)
        OPTIONAL MATCH (h)-[:LOCATED_IN_PROVINCE]->(p:Province)
        OPTIONAL MATCH (h)-[:LOCATED_IN_DISTRICT]->(d:District)
        OPTIONAL MATCH (h)-[:NEAR_ATTRACTION]->(a:Attraction)
        WHERE 1=1 {where_clause}
        RETURN h {{
            .hotel_id,
            .name,
            .type,
            .rating,
            .reviews_count,
            .rate_per_night,
            .price_tier,
            .latitude,
            .longitude,
            province: p.name,
            district: d.name,
            nearby_attraction: a.title
        }} as hotel
        ORDER BY h.rating DESC, h.name ASC
        SKIP $offset
        LIMIT $limit
        """
        
        result = session.run(query, **params)
        hotels = [record["hotel"] for record in result]
        
        return HotelListResponse(
            total=total,
            limit=limit,
            offset=offset,
            hotels=hotels
        )


@router.get("/{hotel_id}", response_model=HotelDetailResponse)
async def get_hotel_detail(
    hotel_id: str,
    driver = Depends(get_neo4j_driver)
):
    """
    Get detailed information about a specific hotel
    
    Includes:
    - Hotel properties
    - Nearby attractions with distances
    - Points of interest
    - Amenities
    """
    with driver.session() as session:
        query = """
        MATCH (h:Hotel {hotel_id: $hotel_id})
        
        // Get hotel properties
        WITH h
        
        // Get nearby attractions
        OPTIONAL MATCH (h)-[r:NEAR_ATTRACTION]->(a:Attraction)
        WITH h, collect({
            name: a.title,
            distance_km: r.distance_km,
            proximity: r.proximity_level,
            travel_time_taxi: r.travel_time_taxi,
            rating: a.rating
        }) as attractions
        
        // Get POIs
        OPTIONAL MATCH (h)-[:NEARBY_POI]->(poi:PointOfInterest)
        WITH h, attractions, collect({
            name: poi.name,
            category: poi.category,
            rating: poi.rating,
            reviews: poi.reviews
        }) as pois
        
        // Get amenities
        OPTIONAL MATCH (h)-[:OFFERS_AMENITY]->(am:Amenity)
        WITH h, attractions, pois, collect(am.name) as amenities
        
        // Get province and district
        OPTIONAL MATCH (h)-[:LOCATED_IN_PROVINCE]->(p:Province)
        OPTIONAL MATCH (h)-[:LOCATED_IN_DISTRICT]->(d:District)
        
        RETURN h {
            .*,
            province: p.name,
            district: d.name
        } as hotel,
        attractions,
        pois,
        amenities
        """
        
        result = session.run(query, hotel_id=hotel_id)
        record = result.single()
        
        if not record:
            raise HTTPException(status_code=404, detail=f"Hotel '{hotel_id}' not found")
        
        # Sanitize Neo4j types
        hotel_data = sanitize_neo4j_types(dict(record["hotel"]))
        attractions_data = sanitize_neo4j_types(record["attractions"])
        pois_data = sanitize_neo4j_types(record["pois"])
        amenities_data = sanitize_neo4j_types(record["amenities"])
        
        return HotelDetailResponse(
            hotel=hotel_data,
            nearby_attractions=attractions_data,
            nearby_pois=pois_data,
            amenities=amenities_data
        )


@router.post("/search", response_model=HotelListResponse)
async def search_hotels(
    query: HotelSearchQuery,
    driver = Depends(get_neo4j_driver)
):
    """
    Advanced hotel search with multiple criteria
    
    Search by:
    - Attraction proximity
    - Price range and tier
    - Rating threshold
    - Required amenities
    - Geographic location
    """
    with driver.session() as session:
        # Build dynamic query
        where_clauses = []
        params = {
            "limit": query.limit,
            "offset": query.offset
        }
        
        cypher_query = "MATCH (h:Hotel)\n"
        
        # Attraction filter
        if query.attraction_name:
            cypher_query += "MATCH (h)-[r:NEAR_ATTRACTION]->(a:Attraction)\n"
            where_clauses.append("(a.title = $attraction_name OR a.name = $attraction_name)")
            params["attraction_name"] = query.attraction_name
            
            if query.max_distance_km:
                where_clauses.append("r.distance_km <= $max_distance")
                params["max_distance"] = query.max_distance_km
        
        # Geography filters
        if query.province:
            cypher_query += "MATCH (h)-[:LOCATED_IN_PROVINCE]->(p:Province)\n"
            where_clauses.append("p.name = $province")
            params["province"] = query.province
        
        if query.district:
            cypher_query += "MATCH (h)-[:LOCATED_IN_DISTRICT]->(d:District)\n"
            where_clauses.append("d.name = $district")
            params["district"] = query.district
        
        # Price filters
        if query.min_price is not None:
            where_clauses.append("h.rate_per_night >= $min_price")
            params["min_price"] = query.min_price
        
        if query.max_price is not None:
            where_clauses.append("h.rate_per_night <= $max_price")
            params["max_price"] = query.max_price
        
        if query.price_tier:
            where_clauses.append("h.price_tier = $price_tier")
            params["price_tier"] = query.price_tier.value
        
        # Rating filter
        if query.min_rating is not None:
            where_clauses.append("h.rating >= $min_rating")
            params["min_rating"] = query.min_rating
        
        # Amenities filter
        if query.amenities:
            cypher_query += """
            MATCH (h)-[:OFFERS_AMENITY]->(am:Amenity)
            WHERE am.name IN $amenities
            WITH h, count(DISTINCT am) as amenity_count
            """
            where_clauses.append("amenity_count = $required_amenity_count")
            params["amenities"] = query.amenities
            params["required_amenity_count"] = len(query.amenities)
        
        # Add WHERE clause
        if where_clauses:
            cypher_query += "WHERE " + " AND ".join(where_clauses) + "\n"
        
        # Return results
        cypher_query += """
        OPTIONAL MATCH (h)-[:LOCATED_IN_PROVINCE]->(prov:Province)
        OPTIONAL MATCH (h)-[:NEAR_ATTRACTION]->(attr:Attraction)
        RETURN h {
            .hotel_id,
            .name,
            .type,
            .rating,
            .reviews_count,
            .rate_per_night,
            .price_tier,
            .latitude,
            .longitude,
            province: prov.name,
            attraction: attr.title
        } as hotel
        ORDER BY h.rating DESC, h.rate_per_night ASC
        SKIP $offset
        LIMIT $limit
        """
        
        result = session.run(cypher_query, **params)
        hotels = [record["hotel"] for record in result]
        
        return HotelListResponse(
            total=len(hotels),
            limit=query.limit,
            offset=query.offset,
            hotels=hotels
        )


@router.post("/recommend", response_model=RecommendationResponse)
async def recommend_hotels(
    query: HotelRecommendationQuery,
    driver = Depends(get_neo4j_driver)
):
    """
    Get personalized hotel recommendations for multi-attraction trips
    
    Optimizes for:
    - **distance**: Minimize total travel distance
    - **price**: Stay within budget
    - **rating**: Maximize hotel quality
    - **balanced**: Balance all factors
    """
    with driver.session() as session:
        # Find hotels near each attraction
        cypher_query = """
        UNWIND $attractions AS attraction_name
        MATCH (a:Attraction)
        WHERE a.title = attraction_name OR a.name = attraction_name
        
        MATCH (h:Hotel)-[r:NEAR_ATTRACTION]->(a)
        WHERE 1=1
        """
        
        params = {
            "attractions": query.attractions,
            "max_results": query.max_results
        }
        
        # Budget filter
        if query.budget_per_night:
            cypher_query += " AND h.rate_per_night <= $budget\n"
            params["budget"] = query.budget_per_night
        
        # Amenities filter
        if query.preferred_amenities:
            cypher_query += """
            OPTIONAL MATCH (h)-[:OFFERS_AMENITY]->(am:Amenity)
            WHERE am.name IN $amenities
            WITH h, a, r, count(DISTINCT am) as amenity_match_count
            """
            params["amenities"] = query.preferred_amenities
        else:
            cypher_query += "WITH h, a, r, 0 as amenity_match_count\n"
        
        # Calculate scores based on optimization criteria
        if query.optimize_for == "distance":
            order_by = "r.distance_km ASC"
        elif query.optimize_for == "price":
            order_by = "h.rate_per_night ASC"
        elif query.optimize_for == "rating":
            order_by = "h.rating DESC"
        else:  # balanced
            cypher_query += """
            WITH h, a, r, amenity_match_count,
                 (5.0 - COALESCE(h.rating, 0)) * 0.3 +
                 (r.distance_km / 20.0) * 0.3 +
                 (h.rate_per_night / 300.0) * 0.2 +
                 (1.0 - (amenity_match_count * 1.0 / CASE WHEN $amenity_count > 0 THEN $amenity_count ELSE 1 END)) * 0.2
                 as balanced_score
            """
            params["amenity_count"] = len(query.preferred_amenities) if query.preferred_amenities else 0
            order_by = "balanced_score ASC"
        
        cypher_query += f"""
        RETURN h {{
            .hotel_id,
            .name,
            .rating,
            .rate_per_night,
            .latitude,
            .longitude
        }} as hotel,
        a.title as attraction,
        r.distance_km as distance,
        amenity_match_count
        ORDER BY {order_by}
        LIMIT $max_results
        """
        
        result = session.run(cypher_query, **params)
        records = list(result)
        
        # Calculate total cost
        recommendations = []
        total_cost = 0.0
        
        for record in records:
            hotel = record["hotel"]
            hotel["attraction"] = record["attraction"]
            hotel["distance_km"] = record["distance"]
            hotel["amenity_matches"] = record["amenity_match_count"]
            
            recommendations.append(hotel)
            rate = hotel.get("rate_per_night") or 0
            total_cost += rate * query.num_nights
        
        # Calculate optimization score (0-100)
        if recommendations:
            avg_rating = sum(h.get("rating") or 0 for h in recommendations) / len(recommendations)
            avg_distance = sum(h.get("distance_km") or 0 for h in recommendations) / len(recommendations)
            avg_price = total_cost / (len(recommendations) * query.num_nights) if total_cost > 0 else 0
            
            # Normalize and combine
            rating_score = (avg_rating / 5.0) * 40  # 40% weight
            distance_score = max(0, (20 - avg_distance) / 20) * 30  # 30% weight
            price_score = max(0, (300 - avg_price) / 300) * 30  # 30% weight
            
            optimization_score = rating_score + distance_score + price_score
        else:
            optimization_score = 0.0
        
        return RecommendationResponse(
            query=query.dict(),
            recommendations=recommendations,
            total_cost=total_cost,
            optimization_score=round(optimization_score, 2)
        )


@router.get("/statistics/overview", response_model=HotelStatistics)
async def get_hotel_statistics(
    driver = Depends(get_neo4j_driver)
):
    """
    Get comprehensive hotel dataset statistics
    
    Includes:
    - Total counts
    - Distribution by price tier, province, rating
    - Average metrics
    - Coverage map
    """
    with driver.session() as session:
        # Overall stats
        query = """
        MATCH (h:Hotel)
        OPTIONAL MATCH (h)-[:NEAR_ATTRACTION]->(a:Attraction)
        OPTIONAL MATCH (h)-[:OFFERS_AMENITY]->(am:Amenity)
        OPTIONAL MATCH (h)-[:NEARBY_POI]->(poi:PointOfInterest)
        OPTIONAL MATCH (h)-[:LOCATED_IN_PROVINCE]->(p:Province)
        
        WITH 
            count(DISTINCT h) as total_hotels,
            count(DISTINCT a) as total_attractions,
            count(DISTINCT am) as total_amenities,
            count(DISTINCT poi) as total_pois,
            avg(h.rate_per_night) as avg_price,
            avg(h.rating) as avg_rating,
            collect(DISTINCT {
                province: p.name,
                hotel: h.hotel_id
            }) as province_data,
            collect(DISTINCT {
                tier: h.price_tier,
                hotel: h.hotel_id
            }) as tier_data,
            collect(DISTINCT {
                rating: toInteger(h.rating),
                hotel: h.hotel_id
            }) as rating_data,
            collect(DISTINCT {
                attraction: a.title,
                hotel: h.hotel_id
            }) as coverage_data
        
        RETURN 
            total_hotels,
            total_attractions,
            total_amenities,
            total_pois,
            avg_price,
            avg_rating,
            province_data,
            tier_data,
            rating_data,
            coverage_data
        """
        
        result = session.run(query)
        record = result.single()
        
        if not record or record["total_hotels"] == 0:
            raise HTTPException(status_code=404, detail="No hotels found in database")
        
        # Handle None values for aggregations
        avg_price = record["avg_price"] if record["avg_price"] is not None else 0.0
        avg_rating = record["avg_rating"] if record["avg_rating"] is not None else 0.0
        
        # Process distributions
        by_province = {}
        for item in record["province_data"]:
            prov = item["province"]
            if prov:
                by_province[prov] = by_province.get(prov, 0) + 1
        
        by_price_tier = {}
        for item in record["tier_data"]:
            tier = item["tier"]
            if tier:
                by_price_tier[tier] = by_price_tier.get(tier, 0) + 1
        
        by_rating = {}
        for item in record["rating_data"]:
            rating = item["rating"]
            if rating and rating > 0:
                star_label = f"{rating}-star"
                by_rating[star_label] = by_rating.get(star_label, 0) + 1
        
        # Coverage map
        coverage_map = {}
        for item in record["coverage_data"]:
            attraction = item["attraction"]
            hotel = item["hotel"]
            if attraction and hotel:
                if attraction not in coverage_map:
                    coverage_map[attraction] = []
                coverage_map[attraction].append(hotel)
        
        return HotelStatistics(
            total_hotels=record["total_hotels"],
            total_attractions_covered=record["total_attractions"],
            by_price_tier=by_price_tier,
            by_province=by_province,
            by_rating=by_rating,
            average_price=round(avg_price, 2),
            average_rating=round(avg_rating, 2),
            total_nearby_pois=record["total_pois"],
            total_amenities=record["total_amenities"],
            coverage_map=coverage_map
        )


@router.get("/near/{attraction_name}")
async def get_hotels_near_attraction(
    attraction_name: str,
    max_distance_km: float = Query(10.0, ge=0, le=50),
    limit: int = Query(10, ge=1, le=50),
    driver = Depends(get_neo4j_driver)
):
    """
    Get hotels near a specific attraction
    
    - **attraction_name**: Name of the attraction
    - **max_distance_km**: Maximum distance in kilometers
    - **limit**: Number of results
    """
    with driver.session() as session:
        query = """
        MATCH (a:Attraction)
        WHERE a.title = $attraction_name OR a.name = $attraction_name
        
        MATCH (h:Hotel)-[r:NEAR_ATTRACTION]->(a)
        WHERE r.distance_km <= $max_distance
        
        OPTIONAL MATCH (h)-[:OFFERS_AMENITY]->(am:Amenity)
        
        WITH h, r, collect(am.name) as amenities
        
        RETURN h {
            .hotel_id,
            .name,
            .type,
            .rating,
            .reviews_count,
            .rate_per_night,
            .check_in_time,
            .check_out_time,
            amenities: amenities
        } as hotel,
        r.distance_km as distance_km,
        r.proximity_level as proximity,
        r.travel_time_taxi as travel_time_taxi
        ORDER BY r.distance_km ASC
        LIMIT $limit
        """
        
        result = session.run(
            query,
            attraction_name=attraction_name,
            max_distance=max_distance_km,
            limit=limit
        )
        
        hotels = []
        for record in result:
            hotel_data = record["hotel"]
            hotel_data["distance_km"] = record["distance_km"]
            hotel_data["proximity"] = record["proximity"]
            hotel_data["travel_time_taxi"] = record["travel_time_taxi"]
            hotels.append(hotel_data)
        
        if not hotels:
            raise HTTPException(
                status_code=404,
                detail=f"No hotels found near '{attraction_name}' within {max_distance_km}km"
            )
        
        return {
            "attraction": attraction_name,
            "max_distance_km": max_distance_km,
            "count": len(hotels),
            "hotels": hotels
        }


@router.post("/ingest", response_model=Dict[str, Any])
async def ingest_hotels(
    file: UploadFile = File(..., description="Hotels JSON file"),
):
    """
    Ingest hotels from uploaded JSON file
    
    **Upload a hotels.json file** containing:
    - Attraction names
    - Hotel details (name, coordinates, pricing, etc.)
    - Nearby places and amenities
    
    **Returns:**
    - Total hotels created
    - Relationships established
    - POIs and amenities added
    - Processing time
    
    **Example usage:**
    ```bash
    curl -X POST "http://localhost:8000/hotels/ingest" \\
      -F "file=@hotels.json"
    ```
    """
    if not file.filename.endswith('.json'):
        raise HTTPException(
            status_code=400,
            detail="Only JSON files are accepted"
        )
    
    try:
        # Read uploaded file
        contents = await file.read()
        data = json.loads(contents.decode('utf-8'))
        
        # Initialize ingestion service
        service = HotelIngestionService()
        
        try:
            # Process the data
            overall_start = time.time()
            
            total_results = {
                "total_attractions": 0,
                "total_hotels_created": 0,
                "total_relationships": 0,
                "total_pois": 0,
                "total_amenities": 0,
                "total_errors": 0,
                "attraction_results": []
            }
            
            # Process each attraction's hotels
            for attraction_data in data.get("attractions", []):
                attraction_name = attraction_data.get("attraction")
                if not attraction_name or not attraction_data.get("hotels"):
                    continue
                
                # Convert to ingestion batch format
                from models.domain.hotel import (
                    HotelIngestionBatch,
                    HotelCreate,
                    GPSCoordinates,
                    NearbyPlace,
                    TransportationOption
                )
                
                hotels = []
                for hotel_data in attraction_data.get("hotels", []):
                    try:
                        # Parse nearby places
                        nearby_places = []
                        for place_data in hotel_data.get("nearby_places", []):
                            transportations = []
                            for trans_data in place_data.get("transportations", []):
                                transportations.append(TransportationOption(**trans_data))
                            
                            gps = place_data.get("gps_coordinates")
                            gps_coords = GPSCoordinates(**gps) if gps else None
                            
                            nearby_places.append(
                                NearbyPlace(
                                    **{**place_data, "transportations": transportations, "gps_coordinates": gps_coords}
                                )
                            )
                        
                        # Create hotel - Handle missing/invalid GPS coordinates
                        gps_data = hotel_data.get("gps_coordinates")
                        if isinstance(gps_data, str) or not gps_data:
                            # Skip hotels with empty/invalid GPS - they must have coordinates
                            total_results["total_errors"] += 1
                            continue
                        
                        # Parse numeric fields safely
                        rate_per_night = hotel_data.get("rate_per_night")
                        if isinstance(rate_per_night, str):
                            # Remove currency symbols and parse
                            rate_per_night = rate_per_night.replace("US$", "").replace("$", "").strip()
                            try:
                                rate_per_night = float(rate_per_night)
                            except:
                                rate_per_night = None
                        
                        rating = hotel_data.get("rating") or hotel_data.get("overall_rating")
                        
                        hotel = HotelCreate(
                            name=hotel_data.get("name"),
                            description=hotel_data.get("description"),
                            link=hotel_data.get("link"),
                            gps_coordinates=GPSCoordinates(**gps_data),
                            rate_per_night=rate_per_night,
                            total_rate=hotel_data.get("total_rate"),
                            check_in_time=hotel_data.get("check_in_time"),
                            check_out_time=hotel_data.get("check_out_time"),
                            property_token=hotel_data.get("property_token"),
                            serpapi_link=hotel_data.get("serpapi_property_details_link"),
                            rating=rating,
                            reviews_count=hotel_data.get("reviews"),
                            images=hotel_data.get("images", []),
                            amenities=hotel_data.get("amenities", []),
                            nearby_places=nearby_places,
                            attraction_name=attraction_name
                        )
                        hotels.append(hotel)
                    except Exception as e:
                        total_results["total_errors"] += 1
                        continue
                
                if hotels:
                    # Create batch
                    batch = HotelIngestionBatch(
                        attraction_name=attraction_name,
                        attraction_description=attraction_data.get("attraction_description"),
                        attraction_geolocation=attraction_data.get("geolocation"),
                        hotel_count=len(hotels),
                        hotels=hotels,
                        metadata=data.get("scrape_metadata", {})
                    )
                    
                    # Ingest
                    batch_result = service.ingest_batch(batch)
                    
                    # Aggregate results
                    total_results["total_attractions"] += 1
                    total_results["total_hotels_created"] += batch_result.hotels_created
                    total_results["total_relationships"] += batch_result.relationships_created
                    total_results["total_pois"] += batch_result.pois_created
                    total_results["total_amenities"] += batch_result.amenities_created
                    total_results["total_errors"] += len(batch_result.errors)
                    
                    total_results["attraction_results"].append({
                        "attraction": attraction_name,
                        "hotels_created": batch_result.hotels_created,
                        "relationships": batch_result.relationships_created,
                        "errors": batch_result.errors if batch_result.errors else []
                    })
            
            total_results["total_time_seconds"] = time.time() - overall_start
            
            return {
                "success": True,
                "message": f"Successfully ingested {total_results['total_hotels_created']} hotels",
                "results": total_results
            }
            
        finally:
            service.close()
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON file format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}"
        )


# ========== Orchestrator Endpoints ==========

@router.post("/orchestrator/call/hotels/search", response_model=OrchestratorSearchResponse, response_model_exclude_none=True)
async def orchestrator_hotel_search(
    request: AccommodationSearchRequest,
    driver = Depends(get_neo4j_driver)
):
    """
    Hotel search endpoint for orchestrator service
    
    Filters hotels by:
    - City and country
    - Star rating range (min/max)
    - Required amenities (normalized: wifi, ac, pool, breakfast, parking, gym, spa, family_rooms)
    - Budget (max price in LKR)
    
    Returns hotels in orchestrator-expected format with:
    - Hotel details
    - Price range in LKR (±10% from base rate)
    - Available amenities
    - Geographic coordinates
    - Neo4j node ID
    
    **Example Request:**
    ```json
    {
        "intent": "info_accommodation",
        "raw_text": "What are 3-star hotels in Colombo?",
        "user_id": "abfe4e3e-06d7-4081-815d-150d92f3070a",
        "session_id": "auto_test",
        "city": "Colombo",
        "country": "Sri Lanka",
        "min_star_rating": 3,
        "max_star_rating": 3,
        "must_have_amenities": ["wifi", "ac"],
        "max_price_lkr": 50000,
        "limit": 10
    }
    ```
    """
    service = OrchestratorHotelService(driver)
    return service.search_hotels(request)


# ========== Management Endpoints ==========

@router.delete("/{hotel_id}")
async def delete_hotel(
    hotel_id: str,
    driver = Depends(get_neo4j_driver)
):
    """
    Delete a specific hotel by ID
    
    This will:
    - Remove the Hotel node
    - Remove all relationships to/from the hotel
    - Clean up orphaned POIs and amenities
    
    Args:
        hotel_id: Unique identifier of the hotel to delete
    
    Returns:
        Deletion confirmation with counts
    """
    with driver.session() as session:
        # First check if hotel exists
        check_result = session.run("""
            MATCH (h:Hotel {hotel_id: $hotel_id})
            RETURN h.name as name
        """, hotel_id=hotel_id)
        
        hotel_record = check_result.single()
        if not hotel_record:
            raise HTTPException(
                status_code=404,
                detail=f"Hotel with ID '{hotel_id}' not found"
            )
        
        hotel_name = hotel_record["name"]
        
        # Delete hotel and its relationships
        result = session.run("""
            MATCH (h:Hotel {hotel_id: $hotel_id})
            OPTIONAL MATCH (h)-[r]-()
            DELETE r, h
            RETURN count(r) as relationships_deleted
        """, hotel_id=hotel_id)
        
        relationships_deleted = result.single()["relationships_deleted"]
        
        # Delete orphaned POIs (not connected to any other hotel)
        result = session.run("""
            MATCH (p:PointOfInterest)
            WHERE NOT (p)<-[:NEARBY_POI]-(:Hotel)
            DELETE p
            RETURN count(p) as pois_deleted
        """)
        pois_deleted = result.single()["pois_deleted"]
        
        # Delete orphaned amenities (not offered by any other hotel)
        result = session.run("""
            MATCH (a:Amenity)
            WHERE NOT (a)<-[:OFFERS_AMENITY]-(:Hotel)
            DELETE a
            RETURN count(a) as amenities_deleted
        """)
        amenities_deleted = result.single()["amenities_deleted"]
        
        return {
            "success": True,
            "message": f"Hotel '{hotel_name}' deleted successfully",
            "hotel_id": hotel_id,
            "hotel_name": hotel_name,
            "relationships_deleted": relationships_deleted,
            "orphaned_pois_cleaned": pois_deleted,
            "orphaned_amenities_cleaned": amenities_deleted
        }


@router.delete("/attraction/{attraction_name}")
async def delete_hotels_by_attraction(
    attraction_name: str,
    confirm: bool = Query(False, description="Set to true to confirm deletion"),
    driver = Depends(get_neo4j_driver)
):
    """
    Delete all hotels associated with a specific attraction
    
    This is useful for:
    - Cleaning up data for a specific location
    - Re-importing fresh data for an attraction
    - Removing outdated hotel listings
    
    Args:
        attraction_name: Name of the attraction
        confirm: Must be true to proceed with deletion
    
    Returns:
        Deletion summary with counts
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion requires confirmation. Add ?confirm=true to URL"
        )
    
    with driver.session() as session:
        # Get hotel count first
        count_result = session.run("""
            MATCH (h:Hotel {attraction: $attraction_name})
            RETURN count(h) as hotel_count, collect(h.name) as hotel_names
        """, attraction_name=attraction_name)
        
        count_record = count_result.single()
        if not count_record or count_record["hotel_count"] == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No hotels found for attraction '{attraction_name}'"
            )
        
        hotel_count = count_record["hotel_count"]
        hotel_names = count_record["hotel_names"]
        
        # Delete hotels and their relationships
        session.run("""
            MATCH (h:Hotel {attraction: $attraction_name})
            OPTIONAL MATCH (h)-[r]-()
            DELETE r, h
        """, attraction_name=attraction_name)
        
        # Clean up orphaned POIs
        result = session.run("""
            MATCH (p:PointOfInterest)
            WHERE NOT (p)<-[:NEARBY_POI]-(:Hotel)
            DELETE p
            RETURN count(p) as pois_deleted
        """)
        pois_deleted = result.single()["pois_deleted"]
        
        # Clean up orphaned amenities
        result = session.run("""
            MATCH (a:Amenity)
            WHERE NOT (a)<-[:OFFERS_AMENITY]-(:Hotel)
            DELETE a
            RETURN count(a) as amenities_deleted
        """)
        amenities_deleted = result.single()["amenities_deleted"]
        
        return {
            "success": True,
            "message": f"Deleted {hotel_count} hotels for attraction '{attraction_name}'",
            "attraction": attraction_name,
            "hotels_deleted": hotel_count,
            "hotel_names": hotel_names,
            "orphaned_pois_cleaned": pois_deleted,
            "orphaned_amenities_cleaned": amenities_deleted
        }


@router.delete("/clear")
async def clear_all_hotels(
    confirm: bool = Query(False, description="Set to true to confirm deletion"),
    driver = Depends(get_neo4j_driver)
):
    """
    **DANGER:** Delete all hotel-related nodes and relationships
    
    This will remove:
    - All Hotel nodes
    - All PointOfInterest nodes
    - All Amenity nodes
    - All related relationships
    
    **Requires confirmation parameter: ?confirm=true**
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion requires confirmation. Add ?confirm=true to URL"
        )
    
    with driver.session() as session:
        # Delete hotels and their relationships
        result = session.run("""
            MATCH (h:Hotel)
            OPTIONAL MATCH (h)-[r]-()
            DELETE r, h
            RETURN count(h) as hotels_deleted
        """)
        hotels_deleted = result.single()["hotels_deleted"]
        
        # Delete orphaned POIs
        result = session.run("""
            MATCH (p:PointOfInterest)
            WHERE NOT (p)<-[:NEARBY_POI]-()
            DELETE p
            RETURN count(p) as pois_deleted
        """)
        pois_deleted = result.single()["pois_deleted"]
        
        # Delete orphaned amenities
        result = session.run("""
            MATCH (a:Amenity)
            WHERE NOT (a)<-[:OFFERS_AMENITY]-()
            DELETE a
            RETURN count(a) as amenities_deleted
        """)
        amenities_deleted = result.single()["amenities_deleted"]
        
        return {
            "success": True,
            "message": "All hotel data deleted",
            "hotels_deleted": hotels_deleted,
            "pois_deleted": pois_deleted,
            "amenities_deleted": amenities_deleted
        }
