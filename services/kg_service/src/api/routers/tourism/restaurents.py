"""Restaurant & food market API endpoints.

Provides endpoints for querying food-related sub-attractions (restaurants,
cafes, markets, street food, bakeries, etc.) within parent attraction locations.
All queries are scoped to the ``Food & Markets`` POI group.
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

router = APIRouter(prefix="/restaurants", tags=["restaurants"])

# POI group this router is scoped to
PREFERRED_POI_CATEGORY: str = "Food & Markets"

# No rejections needed — we are already locking to a single preferred category
REJECTED_POI_CATEGORIES: list[str] = []


# ------------------------------------------------------------------
# Orchestrator endpoint
# ------------------------------------------------------------------

@router.post(
    "/orchestrator/call/restaurants",
    response_model=SubAttractionSearchResponse,
    response_model_exclude_none=True,
)
def search_restaurants_for_orchestrator(
    request: SubAttractionSearchRequest,
    db: DatabaseManager = Depends(get_db_manager),
):
    """
    Search restaurants and food markets for the orchestrator service.

    Always scoped to the **Food & Markets** POI group. The
    ``preferred_poi_category`` field in the request is ignored — the category
    is locked server-side to ``Food & Markets``.

    **Search Strategies:**
    1. **City Only**: All food & market POIs in that location
    2. **POI Name**: Specific restaurant / market name search
    3. **No city**: Food & market POIs across all locations

    Example Request:
    ```json
    {
        "city": "Colombo",
        "country": "Sri Lanka",
        "poi_name": null,
        "days": 1,
        "tags": [],
        "user_id": "abfe4e3e-06d7-4081-815d-150d92f3070a",
        "session_id": "auto_test",
        "query": "What are the best restaurants in Colombo?"
    }
    ```

    Example Response:
    ```json
    {
        "ok": true,
        "city": "Colombo",
        "country": "Sri Lanka",
        "items": [
            {
                "name": "Ministry of Crab",
                "category": "dining",
                "description": "Award-winning seafood restaurant",
                "location": "Old Dutch Hospital, Colombo 01",
                "source": "kg_service",
                "rating": 4.6,
                "coordinates": "6.9344, 79.8428",
                "website": "https://ministryofcrab.com",
                "phone": "+94 11 2342722"
            }
        ],
        "summary": "Found 10 restaurants and food markets in Colombo."
    }
    ```
    """
    try:
        city_display = request.city or "all cities"
        logger.info(
            f"Orchestrator restaurant search: city={city_display}, "
            f"country={request.country}"
        )

        # Override preferred_poi_category — always locked to Food & Markets
        scoped_request = request.copy(update={"preferred_poi_category": PREFERRED_POI_CATEGORY})

        service = OrchestratorSubAttractionService(db.driver)
        response = service.search_sub_attractions(
            scoped_request,
            rejected_categories=REJECTED_POI_CATEGORIES,
        )

        logger.info(f"Found {len(response.items)} restaurants")
        return response

    except Exception as e:
        logger.error(f"Restaurant search failed: {e}")
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
def get_all_restaurants(
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get all restaurants and food markets with optional limit."""
    try:
        logger.info(f"Getting all restaurants with limit={limit}")
        results = db.sub_attractions.get_by_group(PREFERRED_POI_CATEGORY, limit=limit)
        return SubAttractionResponse(
            sub_attractions=results,
            count=len(results),
            query_info={"group": PREFERRED_POI_CATEGORY, "limit": limit},
        )
    except Exception as e:
        logger.error(f"Failed to get restaurants: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get restaurants: {str(e)}")


@router.post("/query", response_model=SubAttractionResponse)
def query_restaurants(
    request: SubAttractionQueryRequest,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Query restaurants with filters.

    Always scoped to the Food & Markets group. Supports additional filtering
    by parent attraction, district, province, name, amenity type, minimum
    rating, and opening hours availability.
    """
    try:
        logger.info(f"Querying restaurants: {request.dict(exclude_none=True)}")

        filters = {
            "group": PREFERRED_POI_CATEGORY,  # always scoped to Food & Markets
            "parent_attraction": request.parent_attraction,
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
        logger.error(f"Failed to query restaurants: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


# ------------------------------------------------------------------
# Initialization — kept for completeness (shared schema with sub-attractions)
# ------------------------------------------------------------------

@router.post("/initialize", response_model=SubAttractionInitResponse)
def initialize_restaurants(
    db: DatabaseManager = Depends(get_db_manager),
):
    """Initialize sub-attraction schema (shared with the restaurants data).

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
            message="Restaurant data initialized successfully",
        )
    except Exception as e:
        logger.error(f"Failed to initialize restaurants: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Restaurant initialization failed: {str(e)}",
        )


# ------------------------------------------------------------------
# Lookup by location
# ------------------------------------------------------------------

@router.get(
    "/parent/{parent_name}",
    response_model=SubAttractionResponse,
)
def get_by_parent_attraction(
    parent_name: str,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get all restaurants / food markets for a parent attraction.

    Args:
        parent_name: Title of the parent attraction (e.g., 'Colombo', 'Kandy').
    """
    try:
        logger.info(f"Getting restaurants for parent: {parent_name}")

        results = db.sub_attractions.query({
            "parent_attraction": parent_name,
            "group": PREFERRED_POI_CATEGORY,
            "limit": 100,
        })

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"No restaurants found for '{parent_name}'",
            )

        return SubAttractionResponse(
            sub_attractions=results,
            count=len(results),
            query_info={"parent_attraction": parent_name, "group": PREFERRED_POI_CATEGORY},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get restaurants by parent: {e}")
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

@router.get("/statistics", response_model=dict)
def get_restaurant_statistics(
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get statistics scoped to the Food & Markets group."""
    try:
        stats = db.sub_attractions.get_statistics()
        group_count = stats.get("byGroup", {}).get(PREFERRED_POI_CATEGORY, 0)
        return {
            "success": True,
            "group": PREFERRED_POI_CATEGORY,
            "total": group_count,
            "statistics": stats,
        }
    except Exception as e:
        logger.error(f"Failed to get restaurant statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{place_id}/nearby-hotels",
    response_model=dict,
)
def get_nearby_hotels(
    place_id: str,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get hotels near a specific restaurant.

    Args:
        place_id: Google Place ID of the restaurant.
    """
    try:
        hotels = db.sub_attractions.get_nearby_hotels(place_id)
        return {
            "restaurant_place_id": place_id,
            "nearby_hotels": hotels,
            "count": len(hotels),
        }
    except Exception as e:
        logger.error(f"Failed to get nearby hotels: {e}")
        raise HTTPException(status_code=500, detail=str(e))
