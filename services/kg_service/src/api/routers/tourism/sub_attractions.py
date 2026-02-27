"""Sub-attraction (POI) API endpoints.

Provides endpoints for managing and querying sub-attractions — individual
points of interest within parent attraction locations (e.g., temples in Kandy,
restaurants in Colombo).
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
from api.dependencies import get_db_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sub-attractions", tags=["sub-attractions"])


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

    Uses the **same request/response contract** as the attractions orchestrator
    endpoint so the orchestrator can call both endpoints uniformly.

    **Search Strategies:**
    1. **City Only** (no poi_category): All POIs in that location
    2. **City + POI Category**: POIs filtered by location and type
    3. **POI Category Only** (no city): POIs across all locations
    4. **POI Name**: Specific POI name search

    Example Request:
    ```json
    {
        "city": "Kandy",
        "country": "Sri Lanka",
        "poi_name": null,
        "poi_category": null,
        "days": 1,
        "tags": [],
        "user_id": "abfe4e3e-06d7-4081-815d-150d92f3070a",
        "session_id": "auto_test",
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
            f"country={request.country}, poi_category={request.poi_category}"
        )

        service = OrchestratorSubAttractionService(db.driver)
        response = service.search_sub_attractions(request)

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
