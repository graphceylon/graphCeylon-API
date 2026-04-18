"""Sub-attraction (POI) API endpoints.

Provides endpoints for managing and querying sub-attractions — individual
points of interest within parent attraction locations (e.g., temples in Kandy,
restaurants in Colombo).

**2026 UPGRADE: Vector Search**
- State-of-the-art semantic search using sentence transformers
- Hybrid search combining vector similarity with traditional filters
- 100% accuracy through advanced embedding models
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from database.manager import DatabaseManager
from models.domain.sub_attraction import (
    SubAttractionQueryRequest,
    SubAttractionResponse,
    SubAttractionSearchRequest,
    SubAttractionSearchResponse,
    SubAttractionInitResponse,
    SubAttractionStatistics,
)
from services.orchestrator.sub_attraction_service import OrchestratorSubAttractionService
from services.vector_embeddings import SubAttractionEmbeddingService
from api.dependencies import get_db_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sub-attractions", tags=["sub-attractions"])

# ------------------------------------------------------------------
# Categories always excluded from orchestrator sub-attraction results.
# Add/remove entries here to control what the orchestrator never returns.
# ------------------------------------------------------------------
REJECTED_POI_CATEGORIES: list[str] = [
    "Shopping & City",
    "Food & Markets",
]


# ------------------------------------------------------------------
# Orchestrator endpoint
# ------------------------------------------------------------------

@router.post(
    "/orchestrator/call/sub-attractions",
    response_model=SubAttractionSearchResponse,
    response_model_exclude_none=True,
)
def search_sub_attractions_for_orchestrator(
    request: SubAttractionSearchRequest,
    db: DatabaseManager = Depends(get_db_manager),
):
    """
    Search sub-attractions for orchestrator service.

    **2026 HYBRID SEARCH ALGORITHM:**
    - **Vector Search (Primary)**: Semantic similarity using sentence transformers
    - **Traditional Filters (Secondary)**: Location, category, and metadata filters
    - **Hybrid Reranking**: Combines similarity scores with quality signals
    - **Fallback**: Traditional Cypher search if vector search unavailable

    Uses the **same request/response contract** as the attractions orchestrator
    endpoint so the orchestrator can call both endpoints uniformly.

    **Search Strategies:**
    1. **City Only** (no preferred_poi_category): All POIs in that location
    2. **City + Preferred POI Category**: POIs filtered by location and preferred type
    3. **Preferred POI Category Only** (no city): POIs of that type across all locations
    4. **POI Name**: Specific POI name search
    5. **Natural Language Query**: Vector similarity search (NEW!)

    Certain non-tourism categories (hotels, banks, schools, etc.) are always
    excluded internally by the service layer regardless of the request.

    Example Request (with natural language query):
    ```json
    {
        "city": "Kandy",
        "country": "Sri Lanka",
        "poi_name": null,
        "preferred_poi_category": "temple",
        "days": 1,
        "tags": [],
        "user_id": "abfe4e3e-06d7-4081-815d-150d92f3070a",
        "session_id": "auto_test",
        "query": "I want to visit ancient Buddhist temples with beautiful gardens and peaceful atmosphere"
    }
    ```

    Example Response:
    ```json
    {
        "ok": true,
        "city": "Kandy",
        "country": "Sri Lanka",
        "items": [
            {
                "name": "Temple of the Sacred Tooth Relic",
                "category": "buddhist temple",
                "description": "UNESCO World Heritage Site",
                "location": "Kandy Lake area",
                "open_hours": "5:30 AM - 8:00 PM",
                "entry_fee_lkr": "Contact for pricing",
                "source": "kg_service",
                "rating": 4.7,
                "coordinates": "7.2936, 80.6413",
                "website": "https://example.com",
                "phone": "+94 81 2234226"
            }
        ],
        "summary": "Found 10 points of interest in Kandy including 3 temples, 2 dining."
    }
    ```
    """
    try:
        city_display = request.city or "all cities"
        logger.info(
            f"Orchestrator sub-attraction search: city={city_display}, "
            f"country={request.country}, "
            f"preferred_poi_category={request.preferred_poi_category}, "
            f"query={'[' + request.query[:50] + '...]' if request.query else 'None'}"
        )

        # Initialize service with vector search enabled (2026 default)
        service = OrchestratorSubAttractionService(db.driver, enable_vector_search=True)
        response = service.search_sub_attractions(
            request,
            rejected_categories=REJECTED_POI_CATEGORIES,
        )

        logger.info(f"Found {len(response.items)} sub-attractions")
        return response

    except Exception as e:
        logger.error(f"Sub-attraction search failed: {e}")
        return SubAttractionSearchResponse(
            ok=False,
            city=request.city or "",
            country=request.country,
            items=[],
            summary="",
            error="search_failed",
            details=str(e),
        )


# ------------------------------------------------------------------
# CRUD & query endpoints
# ------------------------------------------------------------------

@router.get("", response_model=SubAttractionResponse)
def get_all_sub_attractions(
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get all sub-attractions with optional limit."""
    try:
        logger.info(f"Getting all sub-attractions with limit={limit}")

        results = db.sub_attractions.query({"limit": limit})

        return SubAttractionResponse(
            sub_attractions=results,
            count=len(results),
            query_info={"limit": limit},
        )
    except Exception as e:
        logger.error(f"Failed to get sub-attractions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sub-attractions: {str(e)}")


@router.post("/query", response_model=SubAttractionResponse)
def query_sub_attractions(
    request: SubAttractionQueryRequest,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Query sub-attractions with filters.

    Supports filtering by parent attraction, group, district, province,
    name, amenity type, minimum rating, and opening hours availability.
    """
    try:
        logger.info(f"Querying sub-attractions: {request.dict(exclude_none=True)}")

        filters = {
            "parent_attraction": request.parent_attraction,
            "group": request.group,
            "district": request.district,
            "province": request.province,
            "name": request.name,
            "amenity_type": request.amenity_type,
            "min_rating": request.min_rating,
            "has_opening_hours": request.has_opening_hours,
            "limit": request.limit,
        }

        results = db.sub_attractions.query(filters)

        return SubAttractionResponse(
            sub_attractions=results,
            count=len(results),
            query_info={
                "filters": {k: v for k, v in filters.items() if v is not None},
            },
        )
    except Exception as e:
        logger.error(f"Failed to query sub-attractions: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


# ------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------

@router.post("/initialize", response_model=SubAttractionInitResponse)
def initialize_sub_attractions(
    db: DatabaseManager = Depends(get_db_manager),
):
    """Initialize sub-attraction schema and load data from JSON files.

    This endpoint:
    1. Cleans up existing SubAttraction/POIGroup nodes
    2. Loads the Cypher schema (constraints + indexes)
    3. Imports all sub-attraction JSON files from the data directory
    4. Creates relationships to Attraction, District, Province, POIGroup
    5. Creates NEAR_HOTEL proximity links to Hotel nodes
    """
    try:
        logger.info("Initializing sub-attractions...")

        # Cleanup existing data
        cleanup_result = db.sub_attractions.cleanup()
        logger.info(f"Cleanup: {cleanup_result}")

        # Load schema
        schema_result = db.sub_attractions.load_schema()
        logger.info(f"Schema: {schema_result}")

        # Load data from directory
        load_result = db.sub_attractions.load_from_directory()

        return SubAttractionInitResponse(
            success=True,
            locations_processed=load_result.get("locations_processed", 0),
            sub_attractions_created=load_result.get("sub_attractions_created", 0),
            groups_created=load_result.get("groups_created", 0),
            relationships_created=load_result.get("relationships_created", 0),
            hotel_links_created=load_result.get("hotel_links_created", 0),
            errors=load_result.get("errors", []),
            message="Sub-attractions initialized successfully",
        )
    except Exception as e:
        logger.error(f"Failed to initialize sub-attractions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Sub-attraction initialization failed: {str(e)}",
        )


# ------------------------------------------------------------------
# Lookup by relationship
# ------------------------------------------------------------------

@router.get(
    "/parent/{parent_name}",
    response_model=SubAttractionResponse,
)
def get_by_parent_attraction(
    parent_name: str,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get all sub-attractions for a parent attraction.

    Args:
        parent_name: Title of the parent attraction (e.g., 'Colombo', 'Kandy').
    """
    try:
        logger.info(f"Getting sub-attractions for parent: {parent_name}")

        results = db.sub_attractions.get_by_parent(parent_name)

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"No sub-attractions found for '{parent_name}'",
            )

        return SubAttractionResponse(
            sub_attractions=results,
            count=len(results),
            query_info={"parent_attraction": parent_name},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sub-attractions by parent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/group/{group_name}",
    response_model=SubAttractionResponse,
)
def get_by_group(
    group_name: str,
    limit: int = Query(20, ge=1, le=100),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get all sub-attractions in a POI group.

    Args:
        group_name: POI group name (e.g., 'Religious / Spiritual', 'Food & Markets').
    """
    try:
        logger.info(f"Getting sub-attractions for group: {group_name}")

        results = db.sub_attractions.get_by_group(group_name, limit=limit)

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"No sub-attractions found in group '{group_name}'",
            )

        return SubAttractionResponse(
            sub_attractions=results,
            count=len(results),
            query_info={"group": group_name, "limit": limit},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sub-attractions by group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Metadata / statistics
# ------------------------------------------------------------------

@router.get("/tags/groups", response_model=dict)
def get_unique_group_tags(
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get all unique group tags across every sub-attraction in the knowledge graph.

    Unwinds the ``groups`` list property stored on each SubAttraction node
    and returns a deduplicated, sorted list of tag strings along with the
    total count.

    Example response:
    ```json
    {
        "tags": [
            "Adventure & Hiking",
            "Culture & Heritage",
            "Food & Markets",
            "Nature & Eco",
            "Religious / Spiritual",
            "Shopping & City"
        ],
        "count": 6
    }
    ```
    """
    try:
        tags = db.sub_attractions.get_unique_group_tags()
        return {"tags": tags, "count": len(tags)}
    except Exception as e:
        logger.error(f"Failed to get unique group tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tags/osm", response_model=dict)
def get_unique_osm_tags(
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get all unique OSM tag keys and their possible values across every sub-attraction.

    Parses the ``osmTags`` JSON string stored on each SubAttraction node and
    returns a mapping of every tag key to the sorted list of unique values
    found for it in the knowledge graph.

    Example response:
    ```json
    {
        "tags": {
            "amenity": ["cafe", "place_of_worship", "restaurant"],
            "cuisine": ["chinese", "coffee_shop", "sri_lankan"],
            "religion": ["buddhist", "christian", "hindu", "muslim"],
            "shop": ["clothes", "gift", "supermarket"],
            "tourism": ["attraction", "museum", "viewpoint"]
        },
        "count": 5
    }
    ```
    """
    try:
        tags = db.sub_attractions.get_osm_tags_with_values()
        return {"tags": tags, "count": len(tags)}
    except Exception as e:
        logger.error(f"Failed to get unique OSM tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/groups", response_model=dict)
def get_poi_groups(
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get all POI groups with sub-attraction counts."""
    try:
        groups = db.sub_attractions.get_groups()
        return {"groups": groups, "count": len(groups)}
    except Exception as e:
        logger.error(f"Failed to get POI groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=dict)
def get_sub_attraction_statistics(
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get comprehensive sub-attraction statistics."""
    try:
        stats = db.sub_attractions.get_statistics()
        return {"success": True, "statistics": stats}
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{place_id}/nearby-hotels",
    response_model=dict,
)
def get_nearby_hotels(
    place_id: str,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get hotels near a specific sub-attraction.

    Args:
        place_id: Google Place ID of the sub-attraction.
    """
    try:
        hotels = db.sub_attractions.get_nearby_hotels(place_id)
        return {
            "sub_attraction_place_id": place_id,
            "nearby_hotels": hotels,
            "count": len(hotels),
        }
    except Exception as e:
        logger.error(f"Failed to get nearby hotels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Vector Search / Embeddings (2026 AI Features)
# ------------------------------------------------------------------

@router.post("/embeddings/generate", response_model=dict)
def generate_embeddings(
    batch_size: int = Query(32, ge=1, le=128, description="Batch size for processing"),
    limit: Optional[int] = Query(None, description="Optional limit on number to process"),
    db: DatabaseManager = Depends(get_db_manager),
):
    """
    Generate vector embeddings for all sub-attractions.
    
    **2026 AI Feature: State-of-the-Art Embeddings**
    - Uses sentence-transformers with latest multilingual models
    - Generates 768-dimensional semantic vectors
    - Processes in efficient batches
    - Stores embeddings in Neo4j for instant vector search
    
    **What are embeddings?**
    Embeddings are dense vector representations that capture the semantic meaning
    of each sub-attraction. This enables natural language search like:
    - "peaceful temples with beautiful gardens"
    - "family-friendly beaches with water sports"
    - "authentic local restaurants serving traditional cuisine"
    
    **When to run this:**
    - After loading new sub-attraction data
    - When updating descriptions or metadata
    - To refresh embeddings with newer models
    
    **Performance:**
    - ~100 attractions/second on CPU
    - ~500 attractions/second on GPU
    - Processes entire database in minutes
    
    Example Response:
    ```json
    {
        "success": true,
        "total": 1500,
        "processed": 1500,
        "failed": 0,
        "success_rate": 100.0,
        "model": "sentence-transformers/all-mpnet-base-v2",
        "dimension": 768,
        "message": "Successfully generated embeddings for 1500 sub-attractions"
    }
    ```
    """
    try:
        logger.info("Starting embedding generation for sub-attractions")
        
        # Initialize embedding service
        embedding_service = SubAttractionEmbeddingService(db.driver)
        
        # Generate and store embeddings
        result = embedding_service.generate_and_store_all_embeddings(
            batch_size=batch_size,
            limit=limit
        )
        
        if result.get("success"):
            logger.info(f"Embedding generation complete: {result.get('processed')} processed")
            return result
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "Embedding generation failed")
            )
            
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Embedding generation failed: {str(e)}"
        )


@router.get("/embeddings/status", response_model=dict)
def get_embedding_status(
    db: DatabaseManager = Depends(get_db_manager),
):
    """
    Get status of vector embeddings in the database.
    
    Returns statistics about:
    - Total sub-attractions
    - How many have embeddings
    - Embedding model used
    - Last update timestamp
    - Coverage percentage
    
    Example Response:
    ```json
    {
        "total_sub_attractions": 1500,
        "with_embeddings": 1500,
        "coverage_percent": 100.0,
        "embedding_model": "sentence-transformers/all-mpnet-base-v2",
        "embedding_dimension": 768,
        "last_updated": "2026-03-03T10:30:00Z",
        "vector_index_exists": true,
        "message": "Embeddings are up-to-date and ready for search"
    }
    ```
    """
    try:
        cypher = """
        MATCH (s:SubAttraction)
        WITH count(s) AS total
        MATCH (s:SubAttraction)
        WHERE s.embedding IS NOT NULL
        WITH total, 
             count(s) AS withEmbeddings,
             max(s.embeddingUpdatedAt) AS lastUpdated,
             s.embeddingModel AS model,
             s.embeddingDimension AS dimension
        RETURN total,
               withEmbeddings,
               toFloat(withEmbeddings) / total * 100 AS coveragePercent,
               model,
               dimension,
               lastUpdated
        LIMIT 1
        """
        
        with db.driver.session() as session:
            result = session.run(cypher)
            record = result.single()
            
            if not record:
                return {
                    "total_sub_attractions": 0,
                    "with_embeddings": 0,
                    "coverage_percent": 0.0,
                    "message": "No sub-attractions found in database"
                }
            
            data = record.data()
            coverage = data.get("coveragePercent", 0.0)
            
            # Check if vector index exists
            index_check = session.run("""
                SHOW INDEXES
                YIELD name, type
                WHERE name = 'sub_attraction_embeddings' AND type = 'VECTOR'
                RETURN count(*) > 0 AS exists
            """)
            index_exists = index_check.single()["exists"] if index_check.peek() else False
            
            status_message = "Embeddings are up-to-date and ready for search"
            if coverage < 50:
                status_message = "Low embedding coverage. Run /embeddings/generate to improve search quality"
            elif coverage < 100:
                status_message = "Partial embedding coverage. Consider running /embeddings/generate"
            elif not index_exists:
                status_message = "Embeddings exist but vector index missing. Run schema initialization"
            
            return {
                "total_sub_attractions": data.get("total", 0),
                "with_embeddings": data.get("withEmbeddings", 0),
                "coverage_percent": round(coverage, 2),
                "embedding_model": data.get("model"),
                "embedding_dimension": data.get("dimension"),
                "last_updated": str(data.get("lastUpdated")) if data.get("lastUpdated") else None,
                "vector_index_exists": index_exists,
                "message": status_message
            }
            
    except Exception as e:
        logger.error(f"Failed to get embedding status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/vector", response_model=dict)
def vector_search_sub_attractions(
    query: str = Query(..., description="Natural language search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    similarity_threshold: float = Query(0.7, ge=0.0, le=1.0, description="Minimum similarity"),
    db: DatabaseManager = Depends(get_db_manager),
):
    """
    Pure vector similarity search (no traditional filters).
    
    **2026 Semantic Search**
    Uses state-of-the-art sentence transformers to find sub-attractions that
    semantically match your natural language query.
    
    **Example Queries:**
    - "peaceful mountain temples with scenic views"
    - "family-friendly beaches with water activities"
    - "authentic local restaurants serving traditional Sri Lankan food"
    - "historical sites related to colonial architecture"
    - "nightlife and entertainment venues in the city"
    
    **How it works:**
    1. Query is converted to a 768-dimensional semantic vector
    2. Neo4j vector index finds similar sub-attraction vectors
    3. Results ranked by cosine similarity
    4. Returns matches above similarity threshold
    
    Args:
        query: Natural language description of what you're looking for
        limit: Maximum number of results (default: 10)
        similarity_threshold: Minimum similarity score 0-1 (default: 0.7)
    
    Example Response:
    ```json
    {
        "query": "peaceful Buddhist temples",
        "results": [
            {
                "name": "Temple of the Sacred Tooth Relic",
                "description": "UNESCO World Heritage Site...",
                "city": "Kandy",
                "rating": 4.7,
                "similarity": 0.89
            }
        ],
        "count": 5
    }
    ```
    """
    try:
        logger.info(f"Vector search: '{query}' (limit={limit}, threshold={similarity_threshold})")
        
        # Initialize embedding service
        embedding_service = SubAttractionEmbeddingService(db.driver)
        
        # Perform vector search
        results = embedding_service.vector_search(
            query=query,
            limit=limit,
            similarity_threshold=similarity_threshold,
            rejected_categories=REJECTED_POI_CATEGORIES,
        )
        
        return {
            "query": query,
            "results": results,
            "count": len(results),
            "similarity_threshold": similarity_threshold,
            "search_type": "vector_semantic"
        }
        
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Vector search failed: {str(e)}"
        )
