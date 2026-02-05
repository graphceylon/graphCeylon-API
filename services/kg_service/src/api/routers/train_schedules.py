"""
Train Schedules API Router

RESTful endpoints for train schedules queries and operations
"""

import logging
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Depends, Body

from database.manager import DatabaseManager
from models.domain.railway import (
    TrainSchedule,
    TrainScheduleQueryRequest,
    TrainScheduleResponse,
    CreateTrainScheduleRequest,
    RouteQueryRequest,
    RouteResponse,
    RouteOption,
    RouteSegment,
    ScheduleStatistics,
    TrainType,
)
from models.domain.transport_orchestrator import (
    TransportSearchRequest,
    TransportSearchResponse,
)
from services.orchestrator_transport_service import OrchestratorTransportService
from models.schemas import WriteResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/railway/schedules", tags=["train-schedules"])


def get_db_manager():
    """Dependency to get database manager - will be overridden by main app."""
    raise HTTPException(status_code=503, detail="Database manager not initialized")


@router.get("", response_model=TrainScheduleResponse)
def get_train_schedules(
    schedule_date: str = Query(..., description="Schedule date (YYYY-MM-DD) - REQUIRED"),
    start_station: Optional[str] = Query(None, description="Filter by departure station"),
    end_station: Optional[str] = Query(None, description="Filter by arrival station"),
    train_type: Optional[TrainType] = Query(None, description="Filter by train type"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results to return"),
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Get train schedules for a specific date with optional filters.
    
    Required:
    - **schedule_date**: Date in YYYY-MM-DD format (e.g., "2026-01-09") - MANDATORY
    
    Optional Filters:
    - **start_station**: Departure station name (e.g., "Colombo Fort")
    - **end_station**: Arrival station name (e.g., "Kandy")
    - **train_type**: Express, Semi Express, Slow, or Intercity
    """
    try:
        logger.info(f"Getting train schedules - from={start_station}, to={end_station}, date={schedule_date}")
        
        schedules_raw = db.railway.get_train_schedules(
            start_station=start_station,
            end_station=end_station,
            schedule_date=schedule_date,
            train_type=train_type.value if train_type else None,
            limit=limit
        )
        
        # Convert to response model - schedules_raw is already a list of schedule dicts
        schedules = []
        for schedule_dict in schedules_raw:
            # Convert numeric fields properly
            distance_val = schedule_dict.get("distance")
            if distance_val is not None:
                try:
                    distance_val = float(distance_val)
                except (ValueError, TypeError):
                    distance_val = None
            
            train_stops_val = schedule_dict.get("train_stops")
            if train_stops_val is not None:
                try:
                    train_stops_val = int(train_stops_val)
                except (ValueError, TypeError):
                    train_stops_val = None
            
            daily_train_count_val = schedule_dict.get("daily_train_count")
            if daily_train_count_val is not None:
                try:
                    daily_train_count_val = int(daily_train_count_val)
                except (ValueError, TypeError):
                    daily_train_count_val = None
            
            schedules.append({
                "schedule_id": schedule_dict.get("schedule_id"),
                "schedule_date": schedule_dict.get("schedule_date"),
                "start_station": schedule_dict.get("start_station"),
                "end_station": schedule_dict.get("end_station"),
                "departure_time": schedule_dict.get("departure_time"),
                "arrival_time": schedule_dict.get("arrival_time"),
                "duration": schedule_dict.get("duration"),
                "train_number": schedule_dict.get("train_number"),
                "train_type": schedule_dict.get("train_type"),
                "distance": distance_val,
                "train_stops": train_stops_val,
                "ends_at": schedule_dict.get("ends_at"),
                "price_2nd_class": schedule_dict.get("price_2nd_class"),
                "price_3rd_class": schedule_dict.get("price_3rd_class"),
                "start_contact": schedule_dict.get("start_contact"),
                "end_contact": schedule_dict.get("end_contact"),
                "first_train_time": schedule_dict.get("first_train_time"),
                "last_train_time": schedule_dict.get("last_train_time"),
                "daily_train_count": daily_train_count_val,
            })
        
        return TrainScheduleResponse(
            schedules=schedules,
            count=len(schedules),
            query_info={
                "start_station": start_station,
                "end_station": end_station,
                "schedule_date": schedule_date,
                "train_type": train_type.value if train_type else None,
                "limit": limit
            }
        )
    except Exception as e:
        logger.error(f"Failed to get train schedules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get train schedules: {str(e)}")


@router.get("/by-train/{train_number}", response_model=TrainScheduleResponse)
def get_schedules_by_train(
    train_number: str,
    schedule_date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get all schedules for a specific train number."""
    try:
        logger.info(f"Getting schedules for train: {train_number}")
        
        # Query schedules
        cypher = """
        MATCH (schedule:TrainSchedule {train_number: $train_number})
        WHERE ($schedule_date IS NULL OR schedule.schedule_date = $schedule_date)
        RETURN schedule
        ORDER BY schedule.departure_time
        """
        
        results = db.execute_cypher(cypher, {
            "train_number": train_number,
            "schedule_date": schedule_date
        })
        
        schedules = []
        for item in results:
            schedule_dict = item.get("schedule", {})
            schedules.append(schedule_dict)
        
        return TrainScheduleResponse(
            schedules=schedules,
            count=len(schedules),
            query_info={
                "train_number": train_number,
                "schedule_date": schedule_date
            }
        )
    except Exception as e:
        logger.error(f"Failed to get schedules for train {train_number}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get schedules: {str(e)}")


@router.post("/find-routes", response_model=RouteResponse)
def find_routes_between_stations(
    request: RouteQueryRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Find possible routes between two stations.
    
    This endpoint finds direct and indirect routes (with transfers) between stations.
    """
    try:
        logger.info(f"Finding routes from {request.start_station} to {request.end_station}")
        
        # Get direct schedules first
        schedules_raw = db.railway.get_train_schedules(
            start_station=request.start_station,
            end_station=request.end_station,
            train_type=request.preferred_train_type.value if request.preferred_train_type else None,
            limit=10
        )
        
        logger.info(f"Retrieved {len(schedules_raw)} raw schedules from database")
        
        routes = []
        skipped_count = 0
        
        # Convert direct schedules to route options
        for schedule_dict in schedules_raw:
            # Validate train_type - assign default if missing or invalid
            train_type_str = schedule_dict.get("train_type")
            if not train_type_str:
                # Assign default train type based on train number pattern or default to Slow
                train_number = schedule_dict.get("train_number", "")
                if "express" in train_number.lower():
                    train_type = TrainType.EXPRESS
                elif "intercity" in train_number.lower():
                    train_type = TrainType.INTERCITY
                else:
                    train_type = TrainType.SLOW  # Default fallback
                logger.info(f"Assigned default train_type '{train_type.value}' to schedule {train_number}")
            else:
                try:
                    train_type = TrainType(train_type_str)
                except ValueError:
                    # Invalid train type, assign default
                    train_type = TrainType.SLOW
                    logger.warning(f"Invalid train_type '{train_type_str}' for {schedule_dict.get('train_number')}, using default: Slow")
            
            # Convert distance to float
            distance_val = schedule_dict.get("distance")
            if distance_val is not None:
                try:
                    distance_km_float = float(distance_val)
                except (ValueError, TypeError):
                    distance_km_float = None
            else:
                distance_km_float = None
            
            # Parse price
            price_2nd = schedule_dict.get("price_2nd_class", "")
            price_3rd = schedule_dict.get("price_3rd_class", "")
            
            try:
                price_2nd_val = float(price_2nd.replace("Rs.", "").replace(",", "").strip()) if price_2nd else None
            except:
                price_2nd_val = None
                
            try:
                price_3rd_val = float(price_3rd.replace("Rs.", "").replace(",", "").strip()) if price_3rd else None
            except:
                price_3rd_val = None
            
            segment = RouteSegment(
                start_station=request.start_station,
                end_station=request.end_station,
                departure_time=schedule_dict.get("departure_time"),
                arrival_time=schedule_dict.get("arrival_time"),
                duration=schedule_dict.get("duration"),
                train_number=schedule_dict.get("train_number"),
                train_type=train_type,
                distance_km=distance_km_float,
                price_2nd_class=price_2nd,
                price_3rd_class=price_3rd,
            )
            
            route = RouteOption(
                segments=[segment],
                total_duration=schedule_dict.get("duration"),
                total_distance_km=distance_km_float,
                transfer_count=0,
                total_price_2nd_class=price_2nd_val,
                total_price_3rd_class=price_3rd_val,
            )
            
            routes.append(route)
        
        logger.info(f"Created {len(routes)} routes (skipped {skipped_count} invalid schedules)")
        
        # If transfers are allowed, find multi-leg routes
        if request.max_transfers > 0 and len(routes) == 0:
            # This would require more complex graph traversal
            # For now, we'll just return direct routes
            logger.info("Multi-leg route finding not yet implemented")
        
        return RouteResponse(
            routes=routes,
            count=len(routes),
            query=request
        )
        
    except Exception as e:
        logger.error(f"Failed to find routes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to find routes: {str(e)}")


@router.get("/statistics", response_model=ScheduleStatistics)
def get_schedule_statistics(db: DatabaseManager = Depends(get_db_manager)):
    """
    Get comprehensive statistics about train schedules.
    
    Returns:
    - Total schedule count
    - Unique trains count
    - Unique routes count
    - Breakdown by train type
    - Date range coverage
    """
    try:
        logger.info("Getting train schedule statistics")
        
        stats = db.railway.get_schedule_statistics()
        
        # Convert to proper format
        schedules_by_type = {
            item['type']: item['count'] 
            for item in stats.get('schedules_by_train_type', []) 
            if item.get('type')
        }
        
        return ScheduleStatistics(
            total_schedules=stats.get('total_schedules', 0),
            schedules_by_train_type=schedules_by_type,
            unique_trains=stats.get('unique_trains', 0),
            unique_routes=stats.get('unique_routes', 0),
            date_range=stats.get('date_range')
        )
    except Exception as e:
        logger.error(f"Failed to get schedule statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.post("/create", response_model=WriteResponse)
def create_train_schedule(
    request: CreateTrainScheduleRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a new train schedule in the knowledge graph."""
    try:
        logger.info(f"Creating train schedule: Train {request.train_number} from {request.start_station} to {request.end_station}")
        
        # Convert Pydantic model to dict
        schedule_data = request.dict()
        
        # Convert enum to string
        if isinstance(schedule_data.get('train_type'), TrainType):
            schedule_data['train_type'] = schedule_data['train_type'].value
        
        result = db.railway.create_train_schedule(schedule_data)
        
        return WriteResponse(
            success=True,
            message=f"Train schedule for train {request.train_number} created successfully",
            data={"schedule_id": result.get("schedule", {}).get("schedule_id")}
        )
    except Exception as e:
        logger.error(f"Failed to create train schedule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create schedule: {str(e)}")


@router.post("/initialize", response_model=dict)
def initialize_train_schedules(db: DatabaseManager = Depends(get_db_manager)):
    """
    Initialize train schedules from the CSV file.
    
    This will load all train schedules into the knowledge graph.
    Note: Railway stations must be loaded first.
    """
    try:
        logger.info("Initializing train schedules from CSV...")
        
        # Path to the schedules CSV file (absolute path from workspace root)
        csv_file = str(Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "kg_service" / "data" / "train_schedule" / "schedules" / "train_schedules.csv")
        
        result = db.railway.load_schedules_from_csv(csv_file)
        
        if result.get("success"):
            return {
                "success": True,
                "message": "Train schedules initialized successfully",
                "total": result.get("total", 0),
                "created": result.get("created", 0),
                "failed": result.get("failed", 0),
                "errors": result.get("errors", [])
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
            
    except Exception as e:
        logger.error(f"Failed to initialize train schedules: {e}")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


@router.get("/connections/{station_name}", response_model=dict)
def get_station_connections(
    station_name: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Get all stations directly connected to a given station.
    
    Returns stations that have direct train routes to/from the specified station.
    """
    try:
        logger.info(f"Getting connections for station: {station_name}")
        
        cypher = """
        MATCH (station:RailwayStation)
        WHERE toLower(station.name) = toLower($station_name)
        
        // Outgoing connections
        OPTIONAL MATCH (station)<-[:DEPARTS_FROM]-(schedule_out:TrainSchedule)-[:ARRIVES_AT]->(dest:RailwayStation)
        WITH station, dest.name as dest_name, count(schedule_out) as out_count
        WITH station, collect(DISTINCT {station: dest_name, direction: 'outgoing', route_count: out_count}) as outgoing
        
        // Incoming connections
        OPTIONAL MATCH (origin:RailwayStation)<-[:DEPARTS_FROM]-(schedule_in:TrainSchedule)-[:ARRIVES_AT]->(station)
        WITH station, outgoing, origin.name as origin_name, count(schedule_in) as in_count
        WITH station, outgoing, collect(DISTINCT {station: origin_name, direction: 'incoming', route_count: in_count}) as incoming
        
        RETURN {
            station: station.name,
            outgoing_connections: [c IN outgoing WHERE c.station IS NOT NULL],
            incoming_connections: [c IN incoming WHERE c.station IS NOT NULL],
            total_connections: size([c IN outgoing WHERE c.station IS NOT NULL]) + size([c IN incoming WHERE c.station IS NOT NULL])
        } as connections
        """
        
        result = db.execute_cypher(cypher, {"station_name": station_name})
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Station not found: {station_name}")
        
        return result[0].get("connections", {})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get station connections: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get connections: {str(e)}")


# ========== Orchestrator Endpoints ==========

@router.post("/orchestrator/call/transport", response_model=TransportSearchResponse, response_model_exclude_none=True)
def orchestrator_transport_search(
    request: TransportSearchRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Transport search endpoint for orchestrator service
    
    Finds transport options (currently trains) between origin and destination.
    
    **Currently Supported:**
    - Train routes from Sri Lanka Railways
    
    **Future Support:**
    - Bus routes
    - Private transport options
    
    **Example Request:**
    ```json
    {
        "origin": "Colombo",
        "destination": "Kandy",
        "city": null,
        "country": "Sri Lanka",
        "time_of_day": null,
        "days": null,
        "budget_level": null,
        "preferred_transport": [],
        "tags": [],
        "user_id": "abfe4e3e-06d7-4081-815d-150d92f3070a",
        "session_id": "auto_test",
        "query": "How can I travel from Colombo to Kandy?"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "ok": true,
        "origin": "Colombo",
        "destination": "Kandy",
        "country": "Sri Lanka",
        "options": [
            {
                "mode": "train",
                "summary": "Colombo Fort to Kandy scenic train route",
                "estimated_time_min": 180,
                "estimated_cost_lkr": 300,
                "tips": "Reserve seats in advance",
                "source": "Sri Lanka Railways"
            }
        ],
        "summary": "Train is the most scenic option"
    }
    ```
    """
    try:
        # Get Neo4j driver from database manager
        driver = db.driver
        
        # Create service instance
        service = OrchestratorTransportService(driver)
        
        # Search for transport options
        return service.search_transport(request)
        
    except Exception as e:
        logger.error(f"Orchestrator transport search failed: {e}")
        return TransportSearchResponse(
            ok=False,
            origin=request.origin,
            destination=request.destination,
            country=request.country,
            options=[],
            summary="",
            error="Transport search failed",
            details=str(e)
        )
