"""
Bus Terminals API Router

RESTful endpoints for bus terminal queries, initialization, and cleanup.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_db_manager
from database.manager import DatabaseManager
from models.domain.bus_schedule import (
    BusTerminalResponse,
    BusTerminalInitResponse,
    BusTerminalStatistics,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bus/terminals", tags=["bus-terminals"])


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _deserialize_terminal(raw: dict) -> dict:
    """Convert flat Neo4j terminal props into a richer response dict."""
    terminal = {
        "name": raw.get("name"),
        "enriched": raw.get("enriched", False),
        "geocoded": raw.get("geocoded", False),
        "province": raw.get("province"),
        "district": raw.get("district"),
        "city": raw.get("city"),
        "town": raw.get("town"),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "formatted_address": raw.get("formatted_address"),
        "google_rating": raw.get("google_rating"),
        "user_ratings_total": raw.get("user_ratings_total"),
        "business_status": raw.get("business_status"),
        "website": raw.get("website"),
        "phone": raw.get("phone"),
        "google_maps_url": raw.get("google_maps_url"),
        "place_types": raw.get("place_types"),
        "vicinity": raw.get("vicinity"),
    }

    # Optionally inflate full google_data from JSON blob
    gdj = raw.get("google_data_json")
    if gdj:
        try:
            terminal["google_data"] = json.loads(gdj)
        except (json.JSONDecodeError, TypeError):
            pass

    return terminal


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("", response_model=BusTerminalResponse)
def get_bus_terminals(
    province: Optional[str] = Query(None, description="Filter by province"),
    district: Optional[str] = Query(None, description="Filter by district"),
    name_pattern: Optional[str] = Query(None, description="Search by terminal name"),
    has_rating: Optional[bool] = Query(None, description="Only terminals with a Google rating"),
    limit: int = Query(50, ge=1, le=500),
    db: DatabaseManager = Depends(get_db_manager),
):
    """
    List bus terminals with optional filters.

    - **province**: e.g. "Western Province"
    - **district**: e.g. "Colombo"
    - **name_pattern**: case-insensitive substring match
    - **has_rating**: restrict to terminals that have a Google rating
    """
    try:
        raw = db.bus_schedules.get_bus_terminals(
            province=province,
            district=district,
            name_pattern=name_pattern,
            has_rating=has_rating,
            limit=limit,
        )

        terminals = [_deserialize_terminal(r.get("terminal", {})) for r in raw]

        return BusTerminalResponse(
            terminals=terminals,
            count=len(terminals),
            query_info={
                "province": province,
                "district": district,
                "name_pattern": name_pattern,
                "has_rating": has_rating,
                "limit": limit,
            },
        )
    except Exception as e:
        logger.error(f"Failed to get bus terminals: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get bus terminals: {e}")


@router.get("/by-name/{terminal_name}", response_model=dict)
def get_terminal_by_name(
    terminal_name: str,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get a specific bus terminal by name."""
    try:
        result = db.bus_schedules.get_terminal_by_name(terminal_name)
        if not result:
            raise HTTPException(status_code=404, detail=f"Bus terminal not found: {terminal_name}")
        return _deserialize_terminal(result.get("terminal", {}))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get terminal {terminal_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get terminal: {e}")


@router.get("/by-province/{province}", response_model=BusTerminalResponse)
def get_terminals_by_province(
    province: str,
    limit: int = Query(200, ge=1, le=500),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get all bus terminals in a specific province."""
    try:
        raw = db.bus_schedules.get_bus_terminals(province=province, limit=limit)
        terminals = [_deserialize_terminal(r.get("terminal", {})) for r in raw]
        return BusTerminalResponse(
            terminals=terminals,
            count=len(terminals),
            query_info={"province": province},
        )
    except Exception as e:
        logger.error(f"Failed to get terminals by province: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-district/{district}", response_model=BusTerminalResponse)
def get_terminals_by_district(
    district: str,
    limit: int = Query(200, ge=1, le=500),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get all bus terminals in a specific district."""
    try:
        raw = db.bus_schedules.get_bus_terminals(district=district, limit=limit)
        terminals = [_deserialize_terminal(r.get("terminal", {})) for r in raw]
        return BusTerminalResponse(
            terminals=terminals,
            count=len(terminals),
            query_info={"district": district},
        )
    except Exception as e:
        logger.error(f"Failed to get terminals by district: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=BusTerminalResponse)
def search_terminals(
    q: str = Query(..., min_length=2, description="Full-text search query"),
    limit: int = Query(20, ge=1, le=100),
    db: DatabaseManager = Depends(get_db_manager),
):
    """Full-text search across bus terminal names and addresses."""
    try:
        raw = db.bus_schedules.search_terminals(q, limit=limit)
        terminals = [_deserialize_terminal(r.get("terminal", {})) for r in raw]
        return BusTerminalResponse(
            terminals=terminals,
            count=len(terminals),
            query_info={"q": q},
        )
    except Exception as e:
        logger.error(f"Terminal search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=BusTerminalStatistics)
def get_terminal_statistics(db: DatabaseManager = Depends(get_db_manager)):
    """Get statistics about bus terminals in the knowledge graph."""
    try:
        stats = db.bus_schedules.get_terminal_statistics()

        by_province = {
            item["province"]: item["count"]
            for item in stats.get("terminals_by_province", [])
            if item.get("province")
        }
        by_district = {
            item["district"]: item["count"]
            for item in stats.get("terminals_by_district", [])
            if item.get("district")
        }

        return BusTerminalStatistics(
            total_terminals=stats.get("total_terminals", 0),
            enriched_terminals=stats.get("enriched_terminals", 0),
            with_rating=stats.get("with_rating", 0),
            operational=stats.get("operational", 0),
            terminals_by_province=by_province,
            terminals_by_district=by_district,
        )
    except Exception as e:
        logger.error(f"Failed to get terminal statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialize", response_model=BusTerminalInitResponse)
def initialize_bus_terminals(db: DatabaseManager = Depends(get_db_manager)):
    """
    Bulk-load all 2 209 bus terminals from the enriched JSON file.

    Also creates the schema (constraints + indexes) if not present.
    """
    try:
        logger.info("Initializing bus terminal schema...")
        db.bus_schedules.load_schema()

        json_file = str(
            Path(__file__).parent.parent.parent.parent.parent.parent.parent
            / "data"
            / "kg_service"
            / "data"
            / "bus_schedule"
            / "bus_terminals.json"
        )

        result = db.bus_schedules.load_terminals_from_json(json_file)

        if result.get("success"):
            return BusTerminalInitResponse(
                success=True,
                total=result.get("total", 0),
                created=result.get("created", 0),
                failed=result.get("failed", 0),
                errors=result.get("errors", []),
                message=f"Loaded {result.get('created', 0)} bus terminals successfully",
            )
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initialize bus terminals: {e}")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {e}")


@router.delete("/cleanup", response_model=dict)
def cleanup_bus_data(db: DatabaseManager = Depends(get_db_manager)):
    """Delete all bus terminals, schedules, and depots from the knowledge graph."""
    try:
        result = db.bus_schedules.cleanup_bus_data()
        if result.get("success"):
            return {
                "success": True,
                "message": (
                    f"Cleanup complete. Deleted "
                    f"{result.get('terminals_deleted', 0)} terminals, "
                    f"{result.get('schedules_deleted', 0)} schedules, "
                    f"{result.get('depots_deleted', 0)} depots"
                ),
                **result,
            }
        raise HTTPException(status_code=500, detail="Cleanup failed")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cleanup bus data: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {e}")
