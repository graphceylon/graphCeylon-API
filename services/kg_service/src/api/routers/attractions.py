"""Attraction-related API endpoints."""

import logging
from fastapi import APIRouter, HTTPException, Depends

from database.manager import DatabaseManager
from models.graph.knowledge_graph import WriteResponse
from models.domain.attraction import (
    AttractionQueryRequest,
    AttractionResponse,
    CreateAttractionRequest,
    AttractionSearchRequest,
    AttractionSearchResponse,
)
from services.orchestrator.attraction_service import OrchestratorAttractionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attractions", tags=["attractions"])


def get_db_manager():
    """Dependency to get database manager - will be overridden by main app."""
    raise HTTPException(status_code=503, detail="Database manager not initialized")


@router.post("/orchestrator/call/attractions", response_model=AttractionSearchResponse, response_model_exclude_none=True)
def search_attractions_for_orchestrator(
    request: AttractionSearchRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Search attractions for orchestrator service using vector similarity search.
    
    This endpoint uses embeddings and vector similarity search on attraction descriptions
    when poi_category is provided, ensuring semantically relevant results filtered by category.
    
    **Features:**
    - **Vector Search**: Uses embeddings to search attraction descriptions semantically
    - **Category Filtering**: Filters by poi_category (e.g., "temple", "museum", "park")
    - **City Filtering**: Results limited to specified city
    - **Relevance Ranking**: Results ranked by similarity score to query
    
    Example Request:
    ```json
    {
        "city": "Kandy",
        "country": "Sri Lanka",
        "poi_category": "temple",
        "days": 2,
        "query": "What are the main tourist attractions in Kandy?"
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
                "category": "temple",
                "description": "Buddhist temple housing the relic of the tooth of Buddha",
                "location": "Sri Dalada Veediya, Kandy",
                "open_hours": "5:30 AM - 8:00 PM",
                "entry_fee_lkr": "1500",
                "source": "kg_service"
            }
        ],
        "summary": "Found 5 attractions in Kandy including 3 temples, 1 garden, 1 museum."
    }
    ```
    
    **Note**: When poi_category is provided, the endpoint uses vector similarity search
    on attraction descriptions for better semantic matching. Without poi_category,
    it falls back to city-based filtering only.
    """
    try:
        logger.info(f"Orchestrator attraction search: city={request.city}, country={request.country}")
        
        # Initialize service
        service = OrchestratorAttractionService(db.driver)
        
        # Search attractions
        response = service.search_attractions(request)
        
        logger.info(f"Found {len(response.items)} attractions")
        return response
        
    except Exception as e:
        logger.error(f"Attraction search failed: {e}")
        return AttractionSearchResponse(
            ok=False,
            city=request.city,
            country=request.country,
            items=[],
            summary="",
            error="Search failed",
            details=str(e)
        )


@router.get("", response_model=AttractionResponse)
def get_all_attractions(
    limit: int = 20,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get all attractions with optional limit."""
    try:
        logger.info(f"Getting all attractions with limit={limit}")
        
        attractions = db.query_attractions({"limit": limit})
        
        return AttractionResponse(
            attractions=attractions,
            count=len(attractions),
            query_info={"limit": limit}
        )
    except Exception as e:
        logger.error(f"Failed to get attractions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get attractions: {str(e)}")


@router.get("/districts", response_model=dict)
def get_districts_with_attractions(db: DatabaseManager = Depends(get_db_manager)):
    """Get all districts that have attractions."""
    try:
        logger.info("Getting districts with attractions")
        
        result = db.execute_cypher("""
            MATCH (d:District)<-[:LOCATED_IN]-(a:Attraction)
            WITH d, count(a) as attraction_count
            ORDER BY d.name
            RETURN d.name as district, attraction_count
        """)
        
        return {
            "districts": result,
            "count": len(result)
        }
    except Exception as e:
        logger.error(f"Failed to get districts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get districts: {str(e)}")


@router.post("/initialize", response_model=dict)
def initialize_attractions(db: DatabaseManager = Depends(get_db_manager)):
    """Initialize attraction schema and load attractions from JSON."""
    try:
        logger.info("Initializing attractions...")
        
        # Cleanup existing relationships first
        cleanup_result = db.cleanup_attractions()
        logger.info(f"Cleanup: {cleanup_result}")
        
        # Load schema
        schema_result = db.load_attractions_schema()
        
        # Load attractions data with clean relationships
        load_result = db.load_attractions_from_json()
        
        return {
            "success": True,
            "cleanup": cleanup_result,
            "schema": schema_result,
            "data": load_result,
            "message": "Attractions initialized successfully"
        }
    except Exception as e:
        logger.error(f"Failed to initialize attractions: {e}")
        raise HTTPException(status_code=500, detail=f"Attraction initialization failed: {str(e)}")


@router.post("/vector-index/create", response_model=dict)
def create_vector_index(db: DatabaseManager = Depends(get_db_manager)):
    """Create vector index for attraction embeddings."""
    try:
        logger.info("Creating vector index...")
        result = db.create_vector_index()
        return result
    except Exception as e:
        logger.error(f"Failed to create vector index: {e}")
        raise HTTPException(status_code=500, detail=f"Vector index creation failed: {str(e)}")


@router.get("/embeddings/status", response_model=dict)
def check_embeddings_status(db: DatabaseManager = Depends(get_db_manager)):
    """Check if embeddings are created for attractions."""
    try:
        logger.info("Checking embeddings status...")
        
        # Check if vector index exists
        index_query = """
        SHOW INDEXES
        YIELD name, type, entityType, labelsOrTypes, properties
        WHERE name = $index_name
        RETURN name, type, entityType, labelsOrTypes, properties
        """
        
        from core.config import settings
        index_result = db.execute_cypher(index_query, {"index_name": settings.vector_index_name})
        
        # Count attractions with and without embeddings
        count_query = """
        MATCH (a:Attraction)
        RETURN 
            count(a) AS total,
            count(a.embedding) AS with_embeddings,
            count(a) - count(a.embedding) AS without_embeddings
        """
        
        count_result = db.execute_cypher(count_query)
        
        return {
            "success": True,
            "index_exists": len(index_result) > 0,
            "index_details": index_result[0] if index_result else None,
            "total_attractions": count_result[0]["total"] if count_result else 0,
            "with_embeddings": count_result[0]["with_embeddings"] if count_result else 0,
            "without_embeddings": count_result[0]["without_embeddings"] if count_result else 0,
            "embeddings_ready": count_result[0]["without_embeddings"] == 0 if count_result else False
        }
    except Exception as e:
        logger.error(f"Failed to check embeddings status: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.post("/embeddings/update", response_model=dict)
def update_embeddings(db: DatabaseManager = Depends(get_db_manager)):
    """Update embeddings for attractions that don't have them."""
    try:
        logger.info("Updating embeddings...")
        result = db.update_embeddings()
        return result
    except Exception as e:
        logger.error(f"Failed to update embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Embedding update failed: {str(e)}")


@router.post("", response_model=WriteResponse)
def create_attraction(
    request: CreateAttractionRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a new attraction."""
    try:
        import datetime
        logger.info(f"Creating new attraction: {request.title}")
        
        attraction_data = {
            "title": request.title,
            "description": request.description,
            "image_url": request.image_url,
            "district": request.district,
            "latitude": request.latitude,
            "longitude": request.longitude,
            "google_place_id": request.google_place_id,
            "rating": request.rating
        }
        
        result = db.create_attraction(attraction_data)
        
        return WriteResponse(
            success=result["success"],
            node_id=result.get("node_id"),
            provenance={
                "operation": "create_attraction",
                "timestamp": datetime.datetime.now().isoformat(),
                "title": request.title
            }
        )
    except Exception as e:
        logger.error(f"Failed to create attraction: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create attraction: {str(e)}")


@router.post("/query", response_model=AttractionResponse)
def query_attractions(
    request: AttractionQueryRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Query attractions with various filters."""
    try:
        logger.info(f"Querying attractions with filters: {request.dict()}")
        
        filters = {
            "district": request.district,
            "province": request.province,
            "title": request.title,
            "has_coordinates": request.has_coordinates,
            "limit": request.limit
        }
        
        attractions = db.query_attractions(filters)
        
        return AttractionResponse(
            attractions=attractions,
            count=len(attractions),
            query_info={
                "filters": {k: v for k, v in filters.items() if v is not None},
                "limit": request.limit
            }
        )
    except Exception as e:
        logger.error(f"Failed to query attractions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query attractions: {str(e)}")


@router.get("/district/{district_name}", response_model=AttractionResponse)
def get_attractions_by_district(
    district_name: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get all attractions in a specific district."""
    try:
        logger.info(f"Getting attractions for district: {district_name}")
        
        attractions = db.get_attractions_by_district(district_name)
        
        if not attractions:
            raise HTTPException(
                status_code=404,
                detail=f"No attractions found for district '{district_name}'"
            )
        
        return AttractionResponse(
            attractions=attractions,
            count=len(attractions),
            query_info={"district": district_name}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get attractions by district: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get attractions: {str(e)}")


@router.get("/province/{province_name}", response_model=AttractionResponse)
def get_attractions_by_province(
    province_name: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get all attractions in a specific province."""
    try:
        logger.info(f"Getting attractions for province: {province_name}")
        
        attractions = db.get_attractions_by_province(province_name)
        
        if not attractions:
            raise HTTPException(
                status_code=404,
                detail=f"No attractions found for province '{province_name}'"
            )
        
        return AttractionResponse(
            attractions=attractions,
            count=len(attractions),
            query_info={"province": province_name}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get attractions by province: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get attractions: {str(e)}")


@router.post("/link", response_model=dict)
def link_attraction_to_district(
    attraction_title: str,
    district_name: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Link an existing attraction to a district."""
    try:
        logger.info(f"Linking attraction '{attraction_title}' to district '{district_name}'")
        
        result = db.link_attraction_to_district(attraction_title, district_name)
        
        return {
            "success": result["success"],
            "result": result.get("result"),
            "message": f"Successfully linked {attraction_title} to {district_name}"
        }
    except Exception as e:
        logger.error(f"Failed to link attraction to district: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to link attraction: {str(e)}")
