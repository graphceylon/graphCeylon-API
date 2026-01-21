"""
Railway and Train Schedule Data Models

Pydantic models for railway stations and train schedules
Aligned with Transportation Domain (Domain 4) in the Knowledge Graph
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, time
from pydantic import BaseModel, Field, validator
from enum import Enum


class TrainType(str, Enum):
    """Train types in Sri Lanka Railway"""
    EXPRESS = "Express"
    SEMI_EXPRESS = "Semi Express"
    SLOW = "Slow"
    INTERCITY = "Intercity"


class TrainClass(str, Enum):
    """Train class categories"""
    FIRST_CLASS = "1st_class"
    SECOND_CLASS = "2nd_class"
    THIRD_CLASS = "3rd_class"


# ========== Nested Models (from enriched JSON) ==========

class Coordinates(BaseModel):
    """GPS coordinates for railway stations"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[str] = Field(None, description="Accuracy level (high, medium, low)")


class MapLinks(BaseModel):
    """Map service links"""
    google_maps_url: Optional[str] = None
    google_maps_coordinates_url: Optional[str] = None
    google_maps_directions_url: Optional[str] = None
    google_maps_satellite_url: Optional[str] = None
    google_earth_url: Optional[str] = None
    google_street_view_url: Optional[str] = None
    coordinates_decimal: Optional[str] = None
    coordinates_dms: Optional[str] = None
    apple_maps_url: Optional[str] = None
    google_maps_place_url: Optional[str] = None


class AdministrativeAreas(BaseModel):
    """Administrative division information"""
    country: Optional[str] = Field(default="Sri Lanka")
    country_code: Optional[str] = Field(default="LK")
    province: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    town: Optional[str] = None
    village: Optional[str] = None
    postal_code: Optional[str] = None
    route: Optional[str] = None
    street_number: Optional[str] = None


class AddressInfo(BaseModel):
    """Complete address information"""
    formatted_address: Optional[str] = None
    administrative_areas: Optional[AdministrativeAreas] = None


class GeocodingMetadata(BaseModel):
    """Geocoding metadata"""
    geocoded_at: Optional[str] = None
    geocoding_service: Optional[str] = Field(default="google_maps")
    geocoding_confidence: Optional[str] = None
    place_id: Optional[str] = None


class GooglePlaceData(BaseModel):
    """Google Places API data"""
    rating: Optional[float] = Field(None, ge=0, le=5)
    user_ratings_total: Optional[int] = Field(None, ge=0)
    place_url: Optional[str] = None
    editorial_summary: Optional[str] = None
    place_name: Optional[str] = None
    icon: Optional[str] = None
    vicinity: Optional[str] = None
    website: Optional[str] = None
    phone_number: Optional[str] = None
    opening_hours: Optional[Dict[str, Any]] = None


class Geolocation(BaseModel):
    """Complete geolocation data"""
    coordinates: Optional[Coordinates] = None
    map_links: Optional[MapLinks] = None
    address_info: Optional[AddressInfo] = None
    geocoding_metadata: Optional[GeocodingMetadata] = None


# ========== Main Models ==========

class RailwayStationBase(BaseModel):
    """Base railway station information"""
    name: str = Field(..., min_length=1, max_length=200, description="Railway station name")
    enriched: bool = Field(default=False, description="Whether station data is enriched")
    geolocation: Optional[Geolocation] = None
    google_place_data: Optional[GooglePlaceData] = None
    enriched_at: Optional[str] = None
    
    # Quick access properties (derived from nested data)
    @property
    def province(self) -> Optional[str]:
        """Get province from geolocation"""
        if self.geolocation and self.geolocation.address_info:
            if self.geolocation.address_info.administrative_areas:
                return self.geolocation.address_info.administrative_areas.province
        return None
    
    @property
    def district(self) -> Optional[str]:
        """Get district from geolocation"""
        if self.geolocation and self.geolocation.address_info:
            if self.geolocation.address_info.administrative_areas:
                return self.geolocation.address_info.administrative_areas.district
        return None
    
    @property
    def latitude(self) -> Optional[float]:
        """Get latitude from geolocation"""
        if self.geolocation and self.geolocation.coordinates:
            return self.geolocation.coordinates.latitude
        return None
    
    @property
    def longitude(self) -> Optional[float]:
        """Get longitude from geolocation"""
        if self.geolocation and self.geolocation.coordinates:
            return self.geolocation.coordinates.longitude
        return None


class RailwayStation(RailwayStationBase):
    """Complete railway station model"""
    station_id: Optional[str] = Field(None, description="Unique station identifier")
    alternative_names: Optional[List[str]] = Field(default_factory=list)
    facilities: Optional[List[str]] = Field(default_factory=list, description="Station facilities")
    platform_count: Optional[int] = Field(None, ge=1, description="Number of platforms")
    contact_number: Optional[str] = None
    is_major_station: bool = Field(default=False, description="Whether this is a major hub station")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Colombo Fort",
                "enriched": True,
                "station_id": "CMB_FORT",
                "is_major_station": True,
                "platform_count": 10,
                "geolocation": {
                    "coordinates": {
                        "latitude": 6.9344,
                        "longitude": 79.8428,
                        "accuracy": "high"
                    }
                }
            }
        }


class TrainScheduleBase(BaseModel):
    """Base train schedule information"""
    schedule_date: str = Field(..., description="Schedule date (YYYY-MM-DD)")
    start_station: str = Field(..., description="Origin station name")
    end_station: str = Field(..., description="Destination station name")
    departure_time: str = Field(..., description="Departure time (HH:MM AM/PM)")
    arrival_time: str = Field(..., description="Arrival time (HH:MM AM/PM)")
    duration: str = Field(..., description="Travel duration (e.g., 2h 30m)")
    train_number: str = Field(..., description="Unique train number")
    train_type: TrainType = Field(..., description="Type of train service")
    distance: Optional[str] = Field(None, description="Distance (e.g., 120.5 km)")
    
    @validator('train_type', pre=True)
    def validate_train_type(cls, v):
        """Convert train type to enum"""
        if isinstance(v, str):
            # Map string values to enum
            type_map = {
                "Express": TrainType.EXPRESS,
                "Semi Express": TrainType.SEMI_EXPRESS,
                "Slow": TrainType.SLOW,
                "Intercity": TrainType.INTERCITY
            }
            return type_map.get(v, TrainType.EXPRESS)
        return v


class TrainSchedule(TrainScheduleBase):
    """Complete train schedule model"""
    schedule_id: Optional[str] = Field(None, description="Unique schedule identifier")
    ends_at: Optional[str] = Field(None, description="Final destination")
    train_stops: Optional[str] = Field(None, description="Comma-separated list of stops")
    
    # Pricing
    price_2nd_class: Optional[str] = Field(None, description="Second class fare (e.g., Rs. 500.00)")
    price_3rd_class: Optional[str] = Field(None, description="Third class fare (e.g., Rs. 260.00)")
    
    # Contacts
    start_contact: Optional[str] = Field(None, description="Starting station contact")
    end_contact: Optional[str] = Field(None, description="Ending station contact")
    
    # Additional info
    first_train_time: Optional[str] = None
    last_train_time: Optional[str] = None
    daily_train_count: Optional[str] = None
    
    @property
    def stops_list(self) -> List[str]:
        """Parse train stops into list"""
        if self.train_stops:
            return [stop.strip() for stop in self.train_stops.split(',')]
        return []
    
    @property
    def distance_km(self) -> Optional[float]:
        """Extract distance in kilometers"""
        if self.distance:
            # Parse "120.5 km" format
            try:
                return float(self.distance.replace('km', '').strip())
            except (ValueError, AttributeError):
                return None
        return None
    
    class Config:
        json_schema_extra = {
            "example": {
                "schedule_date": "2026-01-09",
                "start_station": "Colombo Fort",
                "end_station": "Kandy",
                "departure_time": "06:50 AM",
                "arrival_time": "09:30 AM",
                "duration": "2h 40m",
                "train_number": "1005",
                "train_type": "Express",
                "distance": "120.5 km",
                "price_2nd_class": "Rs. 300.00",
                "price_3rd_class": "Rs. 150.00"
            }
        }


# ========== Request/Response Models ==========

class RailwayStationQueryRequest(BaseModel):
    """Request model for querying railway stations"""
    province: Optional[str] = None
    district: Optional[str] = None
    name_pattern: Optional[str] = Field(None, description="Pattern to match station name")
    limit: int = Field(20, ge=1, le=100)


class RailwayStationResponse(BaseModel):
    """Response model for railway station queries"""
    stations: List[RailwayStation]
    count: int
    query_info: Optional[Dict[str, Any]] = None


class TrainScheduleQueryRequest(BaseModel):
    """Request model for querying train schedules"""
    start_station: Optional[str] = None
    end_station: Optional[str] = None
    schedule_date: Optional[str] = Field(None, description="Date in YYYY-MM-DD format")
    train_type: Optional[TrainType] = None
    limit: int = Field(50, ge=1, le=200)


class TrainScheduleResponse(BaseModel):
    """Response model for train schedule queries"""
    schedules: List[TrainSchedule]
    count: int
    query_info: Optional[Dict[str, Any]] = None


class RouteQueryRequest(BaseModel):
    """Request model for finding routes between stations"""
    start_station: str = Field(..., description="Origin station")
    end_station: str = Field(..., description="Destination station")
    max_transfers: int = Field(2, ge=0, le=3, description="Maximum number of transfers")
    preferred_train_type: Optional[TrainType] = None


class RouteSegment(BaseModel):
    """Single segment of a multi-leg route"""
    start_station: str
    end_station: str
    departure_time: str
    arrival_time: str
    duration: str
    train_number: str
    train_type: TrainType
    distance_km: Optional[float] = None
    price_2nd_class: Optional[str] = None
    price_3rd_class: Optional[str] = None


class RouteOption(BaseModel):
    """Complete route option with possible transfers"""
    segments: List[RouteSegment]
    total_duration: str
    total_distance_km: Optional[float] = None
    transfer_count: int
    total_price_2nd_class: Optional[float] = None
    total_price_3rd_class: Optional[float] = None


class RouteResponse(BaseModel):
    """Response model for route queries"""
    routes: List[RouteOption]
    count: int
    query: RouteQueryRequest


class CreateRailwayStationRequest(BaseModel):
    """Request model for creating a railway station"""
    name: str
    geolocation: Optional[Geolocation] = None
    google_place_data: Optional[GooglePlaceData] = None
    facilities: Optional[List[str]] = None
    platform_count: Optional[int] = None
    contact_number: Optional[str] = None
    is_major_station: bool = False


class CreateTrainScheduleRequest(BaseModel):
    """Request model for creating a train schedule"""
    schedule_date: str
    start_station: str
    end_station: str
    departure_time: str
    arrival_time: str
    duration: str
    train_number: str
    train_type: TrainType
    distance: Optional[str] = None
    train_stops: Optional[str] = None
    price_2nd_class: Optional[str] = None
    price_3rd_class: Optional[str] = None


class StationStatistics(BaseModel):
    """Statistics for railway stations"""
    total_stations: int
    stations_by_province: Dict[str, int]
    stations_by_district: Dict[str, int]
    enriched_stations: int
    major_stations: int


class ScheduleStatistics(BaseModel):
    """Statistics for train schedules"""
    total_schedules: int
    schedules_by_train_type: Dict[str, int]
    unique_trains: int
    unique_routes: int
    date_range: Optional[Dict[str, str]] = None


# ========== Legacy/Backward Compatibility ==========

# Export commonly used types
__all__ = [
    # Enums
    "TrainType",
    "TrainClass",
    # Main Models
    "RailwayStation",
    "RailwayStationBase",
    "TrainSchedule",
    "TrainScheduleBase",
    # Nested Models
    "Coordinates",
    "Geolocation",
    "AdministrativeAreas",
    "GooglePlaceData",
    # Request/Response
    "RailwayStationQueryRequest",
    "RailwayStationResponse",
    "TrainScheduleQueryRequest",
    "TrainScheduleResponse",
    "RouteQueryRequest",
    "RouteResponse",
    "RouteSegment",
    "RouteOption",
    "CreateRailwayStationRequest",
    "CreateTrainScheduleRequest",
    "StationStatistics",
    "ScheduleStatistics",
]
