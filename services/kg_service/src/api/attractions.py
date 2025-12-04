"""Attraction-related API endpoints."""

import logging
from fastapi import APIRouter, HTTPException, Depends

from ..database.manager import DatabaseManager
from ..models.schemas import (
    WriteResponse,
    AttractionQueryRequest,
    AttractionResponse,
    CreateAttractionRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attractions", tags=["attractions"])


def get_db_manager():
    """Dependency to get database manager - will be overridden by main app."""
    raise HTTPException(status_code=503, detail="Database manager not initialized")


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
