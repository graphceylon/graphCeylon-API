"""
Bus Schedule & Terminal Data Models

Pydantic models for bus terminals, schedules, and depots.
Aligned with Transportation Domain in the Knowledge Graph.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ========== Core Entity Models ==========


class BusTerminalRecord(BaseModel):
    """Single bus terminal as stored in JSON."""
    location_name: str = Field(..., description="Name of the bus terminal/stop")
    geocoded: bool = Field(default=False)
    enriched: bool = Field(default=False)
    google_data: Optional[Dict[str, Any]] = Field(default=None, description="Google Maps enrichment data")


class BusTerminalFile(BaseModel):
    """Top-level structure of bus_terminals.json."""
    metadata: Optional[Dict[str, Any]] = None
    locations: List[BusTerminalRecord] = Field(default_factory=list)


class BusStop(BaseModel):
    """A stop along a bus route (from boarding_points / dropping_points)."""
    time: Optional[str] = Field(None, description="Scheduled time at stop (HH:MM)")
    location: str = Field(..., description="Stop location name")


class BusScheduleRecord(BaseModel):
    """A bus schedule row from the CSV."""
    bus_schedule_id: str = Field(..., description="Unique schedule identifier e.g. BB38-2200-PB")
    schedule_date: str = Field(..., alias="date", description="Date YYYY-MM-DD")
    departure_date: str = Field(...)
    departure_time: str = Field(...)
    arrival_date: str = Field(...)
    arrival_time: str = Field(...)
    origin: str = Field(..., alias="from", description="Origin city")
    destination: str = Field(..., alias="to", description="Destination city")
    depot_name: str = Field(...)
    bus_type: str = Field(default="Normal")
    fare: float = Field(..., description="Fare in LKR")
    model: Optional[str] = Field(None, description="Bus model/make")
    route_no: Optional[str] = Field(None, description="Route number")
    seats_available: Optional[int] = Field(None)
    booking_link: Optional[str] = Field(None)
    booking_closing_date: Optional[str] = Field(None)
    booking_closing_time: Optional[str] = Field(None)
    boarding_points: Optional[List[BusStop]] = Field(default_factory=list)
    dropping_points: Optional[List[BusStop]] = Field(default_factory=list)

    class Config:
        populate_by_name = True


# ========== Query / Request Models ==========


class BusTerminalQueryRequest(BaseModel):
    """Query parameters for bus terminals."""
    province: Optional[str] = Field(None, description="Filter by province")
    district: Optional[str] = Field(None, description="Filter by district")
    name_pattern: Optional[str] = Field(None, description="Search by terminal name")
    has_rating: Optional[bool] = Field(None, description="Filter terminals with Google rating")
    limit: int = Field(50, ge=1, le=500)


class BusScheduleQueryRequest(BaseModel):
    """Query parameters for bus schedules."""
    origin: Optional[str] = Field(None, description="Origin city")
    destination: Optional[str] = Field(None, description="Destination city")
    schedule_date: Optional[str] = Field(None, description="Date YYYY-MM-DD")
    depot_name: Optional[str] = Field(None, description="Filter by operating depot")
    max_fare: Optional[float] = Field(None, description="Maximum fare in LKR")
    limit: int = Field(50, ge=1, le=500)


class BusSearchRequest(BaseModel):
    """Orchestrator search request for bus transport."""
    origin: str = Field(..., description="Starting city")
    destination: str = Field(..., description="Ending city")
    city: Optional[str] = Field(None, description="City context")
    country: str = Field(default="Sri Lanka")
    schedule_date: Optional[str] = Field(None, description="Preferred date YYYY-MM-DD")
    budget_level: Optional[str] = Field(None, description="Budget constraint (low/medium/high)")
    tags: List[str] = Field(default_factory=list)
    user_id: str = Field(..., description="User UUID")
    session_id: str = Field(..., description="Session identifier")
    query: str = Field(..., description="User's original query")


# ========== Response Models ==========


class BusTerminalResponse(BaseModel):
    """Response for bus terminal queries."""
    terminals: List[Dict[str, Any]]
    count: int
    query_info: Optional[Dict[str, Any]] = None


class BusScheduleResponse(BaseModel):
    """Response for bus schedule queries."""
    schedules: List[Dict[str, Any]]
    count: int
    query_info: Optional[Dict[str, Any]] = None


class BusTerminalInitResponse(BaseModel):
    """Response for bus terminal bulk initialization."""
    success: bool
    total: int = 0
    created: int = 0
    failed: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    message: str = ""


class BusScheduleInitResponse(BaseModel):
    """Response for bus schedule bulk initialization."""
    success: bool
    total: int = 0
    created: int = 0
    skipped: int = 0
    failed: int = 0
    depots_created: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    message: str = ""


class BusSearchItem(BaseModel):
    """Single bus option in orchestrator response."""
    name: str = Field(..., description="Bus schedule ID / route label")
    category: str = Field(default="Bus", description="Transport category")
    description: str = Field(..., description="Route summary")
    location: str = Field(..., description="Origin → Destination")
    open_hours: Optional[str] = Field(None, description="Departure → Arrival times")
    entry_fee_lkr: Optional[float] = Field(None, description="Fare in LKR")
    source: str = Field(default="SLTB eSeat")
    rating: Optional[float] = None
    coordinates: Optional[Dict[str, float]] = None
    website: Optional[str] = Field(None, description="Booking link")
    phone: Optional[str] = None


class BusSearchResponse(BaseModel):
    """Orchestrator search response for bus transport."""
    ok: bool
    city: Optional[str] = None
    country: str = "Sri Lanka"
    items: List[BusSearchItem] = Field(default_factory=list)
    summary: str = ""
    error: Optional[str] = None
    details: Optional[str] = None


class BusTerminalStatistics(BaseModel):
    """Statistics for bus terminals."""
    total_terminals: int = 0
    enriched_terminals: int = 0
    with_rating: int = 0
    operational: int = 0
    terminals_by_province: Dict[str, int] = Field(default_factory=dict)
    terminals_by_district: Dict[str, int] = Field(default_factory=dict)


class BusScheduleStatistics(BaseModel):
    """Statistics for bus schedules."""
    total_schedules: int = 0
    unique_origins: int = 0
    unique_destinations: int = 0
    unique_depots: int = 0
    fare_range: Optional[Dict[str, float]] = None
    schedules_by_depot: Dict[str, int] = Field(default_factory=dict)
    schedules_by_origin: Dict[str, int] = Field(default_factory=dict)
