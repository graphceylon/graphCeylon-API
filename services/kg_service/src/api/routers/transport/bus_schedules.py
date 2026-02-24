"""
Bus Schedules API Router

RESTful endpoints for bus schedule queries, route finding,
initialization, and the orchestrator search endpoint.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body

from api.dependencies import get_db_manager
from database.manager import DatabaseManager
from models.domain.bus_schedule import (
    BusScheduleResponse,
    BusScheduleInitResponse,
    BusScheduleStatistics,
    BusSearchRequest,
    BusSearchResponse,
)
from services.orchestrator.bus_schedule_service import OrchestratorBusService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bus/schedules", tags=["bus-schedules"])


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _deserialize_schedule(raw: dict) -> dict:
    """Transform flat Neo4j schedule props into a response dict."""
    schedule = {
        "schedule_id": raw.get("schedule_id"),
        "schedule_date": raw.get("schedule_date"),
        "departure_date": raw.get("departure_date"),
        "departure_time": raw.get("departure_time"),
        "arrival_date": raw.get("arrival_date"),
        "arrival_time": raw.get("arrival_time"),
        "origin": raw.get("origin"),
        "destination": raw.get("destination"),
        "depot_name": raw.get("depot_name"),
        "bus_type": raw.get("bus_type"),
        "fare": raw.get("fare"),
        "model": raw.get("model"),
        "route_no": raw.get("route_no"),
        "seats_available": raw.get("seats_available"),
        "booking_link": raw.get("booking_link"),
        "booking_closing_date": raw.get("booking_closing_date"),
        "booking_closing_time": raw.get("booking_closing_time"),
    }

    # Inflate boarding / dropping points from JSON strings
    for key in ("boarding_points_json", "dropping_points_json"):
        val = raw.get(key)
        if val and isinstance(val, str):
            try:
                schedule[key.replace("_json", "")] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                schedule[key.replace("_json", "")] = val
        elif val and isinstance(val, list):
            schedule[key.replace("_json", "")] = val

    return schedule


# ------------------------------------------------------------------
# Query endpoints
# ------------------------------------------------------------------


@router.get("", response_model=BusScheduleResponse)
def get_bus_schedules(
    origin: Optional[str] = Query(None, description="Filter by origin city"),
    destination: Optional[str] = Query(None, description="Filter by destination city"),
    schedule_date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
    depot_name: Optional[str] = Query(None, description="Filter by depot name"),
    max_fare: Optional[float] = Query(None, description="Maximum fare in LKR"),
    limit: int = Query(50, ge=1, le=500),
    db: DatabaseManager = Depends(get_db_manager),
):
    """
    List bus schedules with optional filters.

    - **origin** / **destination**: city names (case-insensitive)
    - **schedule_date**: YYYY-MM-DD
    - **depot_name**: operating depot
    - **max_fare**: upper bound for fare
    """
    try:
        raw_schedules = db.bus_schedules.get_bus_schedules(
            origin=origin,
            destination=destination,
            schedule_date=schedule_date,
            depot_name=depot_name,
            max_fare=max_fare,
            limit=limit,
        )

        schedules = [_deserialize_schedule(s) for s in raw_schedules]

        return BusScheduleResponse(
            schedules=schedules,
            count=len(schedules),
            query_info={
                "origin": origin,
                "destination": destination,
                "schedule_date": schedule_date,
                "depot_name": depot_name,
                "max_fare": max_fare,
                "limit": limit,
            },
        )
    except Exception as e:
        logger.error(f"Failed to get bus schedules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get bus schedules: {e}")


@router.get("/find-routes", response_model=BusScheduleResponse)
def find_bus_routes(
    origin: str = Query(..., description="Origin city (required)"),
    destination: str = Query(..., description="Destination city (required)"),
    schedule_date: Optional[str] = Query(None, description="Date YYYY-MM-DD"),
    limit: int = Query(10, ge=1, le=50),
    db: DatabaseManager = Depends(get_db_manager),
):
    """
    Find bus routes between two cities, sorted by fare then departure time.
    """
    try:
        raw_schedules = db.bus_schedules.find_bus_routes(
            origin=origin,
            destination=destination,
            schedule_date=schedule_date,
            limit=limit,
        )

        schedules = [_deserialize_schedule(s) for s in raw_schedules]

        return BusScheduleResponse(
            schedules=schedules,
            count=len(schedules),
            query_info={
                "origin": origin,
                "destination": destination,
                "schedule_date": schedule_date,
            },
        )
    except Exception as e:
        logger.error(f"Failed to find bus routes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to find bus routes: {e}")


@router.get("/by-depot/{depot_name}", response_model=BusScheduleResponse)
def get_schedules_by_depot(
    depot_name: str,
    limit: int = Query(50, ge=1, le=200),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get all bus schedules operated by a specific depot."""
    try:
        raw_schedules = db.bus_schedules.get_bus_schedules(depot_name=depot_name, limit=limit)
        schedules = [_deserialize_schedule(s) for s in raw_schedules]
        return BusScheduleResponse(
            schedules=schedules,
            count=len(schedules),
            query_info={"depot_name": depot_name},
        )
    except Exception as e:
        logger.error(f"Failed to get schedules by depot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=BusScheduleStatistics)
def get_schedule_statistics(db: DatabaseManager = Depends(get_db_manager)):
    """Get statistics about bus schedules in the knowledge graph."""
    try:
        stats = db.bus_schedules.get_schedule_statistics()

        by_depot = {
            item["depot"]: item["count"]
            for item in stats.get("schedules_by_depot", [])
            if item.get("depot")
        }
        by_origin = {
            item["origin"]: item["count"]
            for item in stats.get("schedules_by_origin", [])
            if item.get("origin")
        }

        fare_range = stats.get("fare_range")
        if fare_range and fare_range.get("min") is not None:
            fare_range_out = {"min": fare_range["min"], "max": fare_range["max"]}
        else:
            fare_range_out = None

        return BusScheduleStatistics(
            total_schedules=stats.get("total_schedules", 0),
            unique_origins=stats.get("unique_origins", 0),
            unique_destinations=stats.get("unique_destinations", 0),
            unique_depots=stats.get("unique_depots", 0),
            fare_range=fare_range_out,
            schedules_by_depot=by_depot,
            schedules_by_origin=by_origin,
        )
    except Exception as e:
        logger.error(f"Failed to get schedule statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Initialization / Cleanup
# ------------------------------------------------------------------


@router.post("/initialize", response_model=BusScheduleInitResponse)
def initialize_bus_schedules(db: DatabaseManager = Depends(get_db_manager)):
    """
    Bulk-load bus schedules from the CSV file.

    Note: bus terminals should be loaded first via ``/bus/terminals/initialize``.
    """
    try:
        logger.info("Initializing bus schedules from CSV...")

        csv_file = str(
            Path(__file__).parent.parent.parent.parent.parent.parent.parent
            / "data"
            / "kg_service"
            / "data"
            / "bus_schedule"
            / "schedules"
            / "bus_schedules_2026-03-10.csv"
        )

        result = db.bus_schedules.load_schedules_from_csv(csv_file)

        if result.get("success"):
            return BusScheduleInitResponse(
                success=True,
                total=result.get("total", 0),
                created=result.get("created", 0),
                skipped=result.get("skipped", 0),
                failed=result.get("failed", 0),
                depots_created=result.get("depots_created", 0),
                errors=result.get("errors", []),
                message=f"Loaded {result.get('created', 0)} bus schedules successfully",
            )
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initialize bus schedules: {e}")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {e}")


# ------------------------------------------------------------------
# Orchestrator endpoint
# ------------------------------------------------------------------


@router.post(
    "/orchestrator/call/bus-schedules",
    response_model=BusSearchResponse,
    response_model_exclude_none=True,
)
def orchestrator_bus_search(
    request: BusSearchRequest,
    db: DatabaseManager = Depends(get_db_manager),
):
    """
    Orchestrator endpoint for bus schedule search.

    Finds bus options between origin and destination, following the
    standard orchestrator response contract.
    """
    try:
        service = OrchestratorBusService(db.driver)
        return service.search_bus_schedules(request)
    except Exception as e:
        logger.error(f"Orchestrator bus search failed: {e}")
        return BusSearchResponse(
            ok=False,
            city=request.city,
            country=request.country,
            items=[],
            summary="",
            error="Bus search failed",
            details=str(e),
        )
