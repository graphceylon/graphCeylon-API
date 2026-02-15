"""
Railway Stations API Router

RESTful endpoints for railway stations queries and operations
"""

import logging
import json
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Depends

from database.manager import DatabaseManager
from models.domain.railway import (
    RailwayStation,
    RailwayStationQueryRequest,
    RailwayStationResponse,
    CreateRailwayStationRequest,
    StationStatistics,
)
from models.graph.knowledge_graph import WriteResponse
from api.dependencies import get_db_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/railway/stations", tags=["railway-stations"])


def deserialize_station(station_dict: dict) -> dict:
    """Helper function to deserialize station data from Neo4j format."""
    station = {
        "name": station_dict.get("name"),
        "station_id": station_dict.get("station_id"),
        "enriched": station_dict.get("enriched", False),
        "is_major_station": station_dict.get("is_major_station", False),
        "platform_count": station_dict.get("platform_count"),
        "contact_number": station_dict.get("contact_number"),
        "facilities": station_dict.get("facilities", []),
        "alternative_names": station_dict.get("alternative_names", []),
        "enriched_at": station_dict.get("enriched_at"),
    }
    
    # Deserialize complete geolocation data from JSON
    geolocation_json = station_dict.get("geolocation_json")
    if geolocation_json:
        try:
            station["geolocation"] = json.loads(geolocation_json)
        except (json.JSONDecodeError, TypeError):
            # Fallback to constructing from flat fields
            if station_dict.get("latitude") and station_dict.get("longitude"):
                station["geolocation"] = {
                    "coordinates": {
                        "latitude": station_dict.get("latitude"),
                        "longitude": station_dict.get("longitude"),
                        "accuracy": station_dict.get("coordinates_accuracy")
                    },
                    "address_info": {
                        "administrative_areas": {
                            "province": station_dict.get("province"),
                            "district": station_dict.get("district"),
                            "city": station_dict.get("city"),
                        }
                    }
                }
    elif station_dict.get("latitude") and station_dict.get("longitude"):
        # Fallback to flat fields if JSON not available
        station["geolocation"] = {
            "coordinates": {
                "latitude": station_dict.get("latitude"),
                "longitude": station_dict.get("longitude"),
                "accuracy": station_dict.get("coordinates_accuracy")
            },
            "address_info": {
                "administrative_areas": {
                    "province": station_dict.get("province"),
                    "district": station_dict.get("district"),
                    "city": station_dict.get("city"),
                }
            }
        }
    
    # Deserialize complete Google Place data from JSON
    google_place_json = station_dict.get("google_place_data_json")
    if google_place_json:
        try:
            station["google_place_data"] = json.loads(google_place_json)
        except (json.JSONDecodeError, TypeError):
            # Fallback to constructing from flat fields
            if station_dict.get("google_rating"):
                station["google_place_data"] = {
                    "rating": station_dict.get("google_rating"),
                    "user_ratings_total": station_dict.get("google_ratings_total"),
                    "place_url": station_dict.get("google_place_url"),
                }
    elif station_dict.get("google_rating"):
        # Fallback to flat fields if JSON not available
        station["google_place_data"] = {
            "rating": station_dict.get("google_rating"),
            "user_ratings_total": station_dict.get("google_ratings_total"),
            "place_url": station_dict.get("google_place_url"),
        }
    
    return station


# ========== Endpoints ==========


@router.get("", response_model=RailwayStationResponse)
def get_railway_stations(
    province: Optional[str] = Query(None, description="Filter by province"),
    district: Optional[str] = Query(None, description="Filter by district"),
    name_pattern: Optional[str] = Query(None, description="Search by station name pattern"),
    is_major: Optional[bool] = Query(None, description="Filter major stations only"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Get all railway stations with optional filters.
    
    Filters:
    - **province**: Filter by province (e.g., "Western Province")
    - **district**: Filter by district (e.g., "Colombo")
    - **name_pattern**: Search station names (case-insensitive)
    - **is_major**: Get only major stations (true/false)
    """
    try:
        logger.info(f"Getting railway stations - province={province}, district={district}, pattern={name_pattern}")
        
        stations_raw = db.railway.get_railway_stations(
            province=province,
            district=district,
            name_pattern=name_pattern,
            is_major=is_major,
            limit=limit
        )
        
        # Convert to response model
        stations = []
        for item in stations_raw:
            station_dict = item.get("station", {})
            stations.append(deserialize_station(station_dict))
        
        return RailwayStationResponse(
            stations=stations,
            count=len(stations),
            query_info={
                "province": province,
                "district": district,
                "name_pattern": name_pattern,
                "is_major": is_major,
                "limit": limit
            }
        )
    except Exception as e:
        logger.error(f"Failed to get railway stations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get railway stations: {str(e)}")


@router.get("/by-name/{station_name}", response_model=dict)
def get_station_by_name(
    station_name: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get a specific railway station by name."""
    try:
        logger.info(f"Getting railway station: {station_name}")
        
        result = db.railway.get_station_by_name(station_name)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Railway station not found: {station_name}")
        
        station_dict = result.get("station", {})
        
        # Deserialize and return complete station data
        return deserialize_station(station_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get station {station_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get station: {str(e)}")


@router.get("/by-province/{province}", response_model=RailwayStationResponse)
def get_stations_by_province(
    province: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get all railway stations in a specific province."""
    try:
        logger.info(f"Getting railway stations in province: {province}")
        
        stations_raw = db.railway.get_stations_by_province(province)
        
        stations = []
        for item in stations_raw:
            station_dict = item.get("station", {})
            stations.append(deserialize_station(station_dict))
        
        return RailwayStationResponse(
            stations=stations,
            count=len(stations),
            query_info={"province": province}
        )
    except Exception as e:
        logger.error(f"Failed to get stations by province: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stations: {str(e)}")


@router.get("/by-district/{district}", response_model=RailwayStationResponse)
def get_stations_by_district(
    district: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get all railway stations in a specific district."""
    try:
        logger.info(f"Getting railway stations in district: {district}")
        
        stations_raw = db.railway.get_stations_by_district(district)
        
        stations = []
        for item in stations_raw:
            station_dict = item.get("station", {})
            stations.append(deserialize_station(station_dict))
        
        return RailwayStationResponse(
            stations=stations,
            count=len(stations),
            query_info={"district": district}
        )
    except Exception as e:
        logger.error(f"Failed to get stations by district: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stations: {str(e)}")


@router.get("/statistics", response_model=StationStatistics)
def get_station_statistics(db: DatabaseManager = Depends(get_db_manager)):
    """
    Get comprehensive statistics about railway stations.
    
    Returns:
    - Total station count
    - Breakdown by province
    - Breakdown by district
    - Enrichment status
    - Major station count
    """
    try:
        logger.info("Getting railway station statistics")
        
        stats = db.railway.get_station_statistics()
        
        # Convert to proper format
        stations_by_province = {
            item['province']: item['count'] 
            for item in stats.get('stations_by_province', []) 
            if item.get('province')
        }
        
        stations_by_district = {
            item['district']: item['count'] 
            for item in stats.get('stations_by_district', []) 
            if item.get('district')
        }
        
        return StationStatistics(
            total_stations=stats.get('total_stations', 0),
            stations_by_province=stations_by_province,
            stations_by_district=stations_by_district,
            enriched_stations=stats.get('enriched_stations', 0),
            major_stations=stats.get('major_stations', 0)
        )
    except Exception as e:
        logger.error(f"Failed to get station statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.post("/create", response_model=WriteResponse)
def create_railway_station(
    request: CreateRailwayStationRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a new railway station in the knowledge graph."""
    try:
        logger.info(f"Creating railway station: {request.name}")
        
        # Convert Pydantic model to dict
        station_data = request.dict()
        
        result = db.railway.create_railway_station(station_data)
        
        return WriteResponse(
            success=True,
            message=f"Railway station '{request.name}' created successfully",
            data={"station_id": result.get("station", {}).get("station_id")}
        )
    except Exception as e:
        logger.error(f"Failed to create railway station: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create station: {str(e)}")


@router.post("/initialize", response_model=dict)
def initialize_railway_stations(db: DatabaseManager = Depends(get_db_manager)):
    """
    Initialize railway stations from the enriched JSON file.
    
    This will load all 203 enriched railway stations into the knowledge graph.
    """
    try:
        logger.info("Initializing railway stations from JSON...")
        
        # Path to the enriched stations file (absolute path from workspace root)
        json_file = str(Path(__file__).parent.parent.parent.parent.parent.parent.parent / "data" / "kg_service" / "data" / "train_schedule" / "railway_stations_enriched.json")
        
        result = db.railway.load_stations_from_json(json_file)
        
        if result.get("success"):
            return {
                "success": True,
                "message": "Railway stations initialized successfully",
                "total": result.get("total", 0),
                "created": result.get("created", 0),
                "failed": result.get("failed", 0),
                "errors": result.get("errors", [])
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
            
    except Exception as e:
        logger.error(f"Failed to initialize railway stations: {e}")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


@router.delete("/cleanup", response_model=dict)
def cleanup_railway_data(db: DatabaseManager = Depends(get_db_manager)):
    """Delete all railway stations and schedules from the knowledge graph."""
    try:
        logger.info("Cleaning up railway data...")
        
        result = db.railway.cleanup_railway_data()
        
        if result.get("success"):
            return {
                "success": True,
                "message": f"Cleanup complete. Deleted {result.get('stations_deleted', 0)} stations and {result.get('schedules_deleted', 0)} schedules",
                "stations_deleted": result.get('stations_deleted', 0),
                "schedules_deleted": result.get('schedules_deleted', 0)
            }
        else:
            raise HTTPException(status_code=500, detail="Cleanup failed")
            
    except Exception as e:
        logger.error(f"Failed to cleanup railway data: {e}")
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")
