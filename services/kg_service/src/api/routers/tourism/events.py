"""Event API endpoints.

Provides endpoints for managing and querying events — concerts, exhibitions,
conferences, sports matches, excursions, and other public happenings in
Sri Lanka.

Events belong to the "Event & Activity" domain in the knowledge graph.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from database.manager import DatabaseManager
from models.domain.event import (
    EventQueryRequest,
    EventResponse,
    EventSearchRequest,
    EventSearchResponse,
    EventInitResponse,
    EventStatistics,
)
from services.orchestrator.event_service import OrchestratorEventService
from api.dependencies import get_db_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


# ------------------------------------------------------------------
# Orchestrator endpoint
# ------------------------------------------------------------------

@router.post(
    "/orchestrator/call/events",
    response_model=EventSearchResponse,
    response_model_exclude_none=True,
)
def search_events_for_orchestrator(
    request: EventSearchRequest,
    db: DatabaseManager = Depends(get_db_manager),
):
    """
    Search events for orchestrator service.

    Uses the **same request/response contract** as the attractions orchestrator
    endpoint so the orchestrator can call all endpoints uniformly.

    **Search Strategies:**
    1. **City Only**: Events at venues matching that city
    2. **City + POI Category**: Filtered by venue + event type
    3. **POI Category Only**: Events of that type across all venues
    4. **POI Name**: Search by specific event name
    5. **Tags**: Match against event hashtags / types

    Example Request:
    ```json
    {
        "city": "Colombo",
        "country": "Sri Lanka",
        "poi_name": null,
        "poi_category": "Music/ Concert",
        "days": 2,
        "tags": [],
        "user_id": "abfe4e3e-06d7-4081-815d-150d92f3070a",
        "session_id": "auto_test",
        "query": "What concerts are happening in Colombo?"
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
                "name": "FACETS 2026 INTERNATIONAL GEM & JEWELLERY SHOW",
                "category": "Fair/ Exhibition",
                "description": "...",
                "location": "CINNAMON LIFE AT CITY OF DREAMS",
                "open_hours": "3-Jan-2026 – 5-Jan-2026 | 08:00 am – 08:00 pm",
                "entry_fee_lkr": "Contact organizer",
                "source": "kg_service"
            }
        ],
        "summary": "Found 15 events in Colombo including 5 Music/ Concerts, 3 Fair/ Exhibitions."
    }
    ```
    """
    try:
        city_display = request.city or "all cities"
        logger.info(
            f"Orchestrator event search: city={city_display}, "
            f"country={request.country}, poi_category={request.poi_category}"
        )

        service = OrchestratorEventService(db.driver)
        response = service.search_events(request)

        logger.info(f"Found {len(response.items)} events")
        return response

    except Exception as e:
        logger.error(f"Event search failed: {e}")
        return EventSearchResponse(
            ok=False,
            city=request.city or "",
            country=request.country,
            items=[],
            summary="",
            error="search_failed",
            details=str(e),
        )


# ------------------------------------------------------------------
# General query
# ------------------------------------------------------------------

@router.get("", response_model=EventResponse)
def list_events(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    venue: Optional[str] = Query(None, description="Filter by venue"),
    organizer: Optional[str] = Query(None, description="Filter by organizer"),
    date_from: Optional[str] = Query(None, description="ISO date lower bound"),
    date_to: Optional[str] = Query(None, description="ISO date upper bound"),
    q: Optional[str] = Query(None, description="Free-text search"),
    limit: int = Query(20, ge=1, le=100),
    db: DatabaseManager = Depends(get_db_manager),
):
    """List events with optional filters."""
    try:
        params = {
            "event_type": event_type,
            "venue": venue,
            "organizer": organizer,
            "date_from": date_from,
            "date_to": date_to,
            "query": q,
            "limit": limit,
        }
        results = db.events.query(params)
        return EventResponse(
            success=True,
            events=results,
            count=len(results),
        )
    except Exception as e:
        logger.error(f"Event query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=EventResponse)
def query_events(
    request: EventQueryRequest,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Query events via POST body."""
    try:
        params = request.model_dump(exclude_none=True)
        results = db.events.query(params)
        return EventResponse(
            success=True,
            events=results,
            count=len(results),
        )
    except Exception as e:
        logger.error(f"Event query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------

@router.post("/initialize", response_model=EventInitResponse)
def initialize_events(
    db: DatabaseManager = Depends(get_db_manager),
):
    """Initialize event schema and load data from events.json.

    This endpoint:
    1. Cleans up existing Event/EventType/Venue/Organizer nodes
    2. Loads the Cypher schema (constraints + indexes)
    3. Imports all events from events.json
    4. Creates relationships (HAS_TYPE, HELD_AT, ORGANIZED_BY, BELONGS_TO_DOMAIN)
    5. Wires temporal links (IN_YEAR, IN_MONTH)
    """
    try:
        logger.info("Initializing events...")

        # Cleanup existing data
        cleanup_result = db.events.cleanup()
        logger.info(f"Cleanup: {cleanup_result}")

        # Load schema
        schema_result = db.events.load_schema()
        logger.info(f"Schema: {schema_result}")

        # Load data
        load_result = db.events.load_from_file()

        return EventInitResponse(
            success=True,
            events_created=load_result.get("events_created", 0),
            event_types_created=load_result.get("event_types_created", 0),
            venues_created=load_result.get("venues_created", 0),
            organizers_created=load_result.get("organizers_created", 0),
            relationships_created=load_result.get("relationships_created", 0),
            errors=load_result.get("errors", []),
            message="Events initialized successfully",
        )
    except Exception as e:
        logger.error(f"Failed to initialize events: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Event initialization failed: {str(e)}",
        )


# ------------------------------------------------------------------
# Lookup by relationship
# ------------------------------------------------------------------

@router.get("/type/{event_type}", response_model=EventResponse)
def get_events_by_type(
    event_type: str,
    limit: int = Query(20, ge=1, le=100),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get events filtered by event type."""
    results = db.events.get_by_type(event_type, limit=limit)
    return EventResponse(success=True, events=results, count=len(results))


@router.get("/venue/{venue_name}", response_model=EventResponse)
def get_events_by_venue(
    venue_name: str,
    limit: int = Query(20, ge=1, le=100),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get events held at a specific venue."""
    results = db.events.get_by_venue(venue_name, limit=limit)
    return EventResponse(success=True, events=results, count=len(results))


@router.get("/organizer/{organizer_name}", response_model=EventResponse)
def get_events_by_organizer(
    organizer_name: str,
    limit: int = Query(20, ge=1, le=100),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get events by a specific organizer."""
    results = db.events.get_by_organizer(organizer_name, limit=limit)
    return EventResponse(success=True, events=results, count=len(results))


@router.get("/upcoming", response_model=EventResponse)
def get_upcoming_events(
    from_date: Optional[str] = Query(None, description="ISO start date (defaults to today)"),
    limit: int = Query(20, ge=1, le=100),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get upcoming events from a given date."""
    results = db.events.get_upcoming(from_date=from_date, limit=limit)
    return EventResponse(success=True, events=results, count=len(results))


# ------------------------------------------------------------------
# Reference data
# ------------------------------------------------------------------

@router.get("/types")
def get_event_types(db: DatabaseManager = Depends(get_db_manager)):
    """Get all event types with counts."""
    return db.events.get_event_types()


@router.get("/venues")
def get_venues(
    limit: int = Query(50, ge=1, le=200),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get venues with event counts."""
    return db.events.get_venues(limit=limit)


@router.get("/organizers")
def get_organizers(
    limit: int = Query(50, ge=1, le=200),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get organizers with event counts."""
    return db.events.get_organizers(limit=limit)


# ------------------------------------------------------------------
# Statistics
# ------------------------------------------------------------------

@router.get("/statistics", response_model=EventStatistics)
def get_event_statistics(
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get event knowledge-graph statistics."""
    stats = db.events.get_statistics()
    return EventStatistics(**stats)
