"""Common models shared across multiple domain models.

This module contains reusable Pydantic models for geolocation, coordinates,
administrative areas, and other shared data structures. These models eliminate
duplication across attraction, railway, and hotel models.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ========== Geographic Models ==========

class CoordinatesModel(BaseModel):
    """GPS coordinates with optional accuracy information.
    
    Used across attractions, railway stations, and hotels.
    """
    latitude: float = Field(..., ge=-90, le=90, description="Latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude")
    accuracy: Optional[str] = Field(None, description="Coordinate accuracy level")
    
    class Config:
        json_schema_extra = {
            "example": {
                "latitude": 6.9271,
                "longitude": 79.8612,
                "accuracy": "high"
            }
        }


class MapLinksModel(BaseModel):
    """Links to various map services for a location."""
    google_maps_url: Optional[str] = Field(None, description="Google Maps URL")
    google_maps_coordinates_url: Optional[str] = Field(None, description="Google Maps coordinates URL")
    google_maps_directions_url: Optional[str] = Field(None, description="Google Maps directions URL")
    google_maps_satellite_url: Optional[str] = Field(None, description="Google Maps satellite view URL")
    google_earth_url: Optional[str] = Field(None, description="Google Earth URL")
    google_street_view_url: Optional[str] = Field(None, description="Google Street View URL")
    coordinates_decimal: Optional[str] = Field(None, description="Coordinates in decimal format")
    coordinates_dms: Optional[str] = Field(None, description="Coordinates in DMS format")
    apple_maps_url: Optional[str] = Field(None, description="Apple Maps URL")
    google_maps_place_url: Optional[str] = Field(None, description="Google Maps place URL")


class AdministrativeAreasModel(BaseModel):
    """Administrative division information for locations.
    
    Provides hierarchical location data from country down to street level.
    """
    country: Optional[str] = Field(None, description="Country name")
    country_code: Optional[str] = Field(None, description="Country code (ISO 3166-1)")
    province: Optional[str] = Field(None, description="Province/state name")
    district: Optional[str] = Field(None, description="District name")
    city: Optional[str] = Field(None, description="City name")
    town: Optional[str] = Field(None, description="Town name")
    village: Optional[str] = Field(None, description="Village name")
    postal_code: Optional[str] = Field(None, description="Postal code")
    route: Optional[str] = Field(None, description="Route/road name")
    street_number: Optional[str] = Field(None, description="Street number")


class AddressInfoModel(BaseModel):
    """Complete address information combining formatted text and hierarchical areas."""
    formatted_address: Optional[str] = Field(None, description="Human-readable formatted address")
    administrative_areas: Optional[AdministrativeAreasModel] = Field(None, description="Structured administrative divisions")


class GeocodingMetadataModel(BaseModel):
    """Metadata about geocoding operations and data sources."""
    geocoded_at: Optional[str] = Field(None, description="Geocoding timestamp (ISO format)")
    geocoding_service: Optional[str] = Field(None, description="Geocoding service used (e.g., 'google_maps')")
    geocoding_confidence: Optional[str] = Field(None, description="Confidence level (high/medium/low)")
    place_id: Optional[str] = Field(None, description="External place identifier")


class GeolocationModel(BaseModel):
    """Complete geolocation data for any location-based entity.
    
    Combines coordinates, map links, address info, and geocoding metadata
    into a single comprehensive model.
    """
    coordinates: Optional[CoordinatesModel] = Field(None, description="GPS coordinates")
    map_links: Optional[MapLinksModel] = Field(None, description="Links to map services")
    address_info: Optional[AddressInfoModel] = Field(None, description="Address information")
    geocoding_metadata: Optional[GeocodingMetadataModel] = Field(None, description="Geocoding metadata")


# ========== Google Places Models ==========

class GooglePlaceDataModel(BaseModel):
    """Google Places API data for locations.
    
    Used for attractions, railway stations that have Google Place information.
    """
    rating: Optional[float] = Field(None, ge=0, le=5, description="Google rating (0-5)")
    user_ratings_total: Optional[int] = Field(None, ge=0, description="Total number of ratings")
    reviews: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="User reviews")
    photos: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Photos")
    website: Optional[str] = Field(None, description="Website URL")
    phone_number: Optional[str] = Field(None, description="Phone number")
    opening_hours: Optional[Dict[str, Any]] = Field(None, description="Opening hours data")
    price_level: Optional[int] = Field(None, ge=0, le=4, description="Price level (0-4)")
    place_types: Optional[List[str]] = Field(default_factory=list, description="Google place types")
    place_url: Optional[str] = Field(None, description="Google Maps place URL")
    editorial_summary: Optional[str] = Field(None, description="Editorial summary from Google")
    place_name: Optional[str] = Field(None, description="Place name from Google")
    icon: Optional[str] = Field(None, description="Icon URL")
    vicinity: Optional[str] = Field(None, description="Vicinity/neighborhood description")


# ========== Common Response Models ==========

class PaginatedResponse(BaseModel):
    """Base model for paginated list responses."""
    count: int = Field(..., description="Number of items in this response")
    total: Optional[int] = Field(None, description="Total number of items available")
    limit: int = Field(..., description="Maximum items per page")
    offset: int = Field(default=0, description="Starting offset")


class QueryMetadata(BaseModel):
    """Common metadata for query responses."""
    query_time_ms: Optional[float] = Field(None, description="Query execution time in milliseconds")
    filters_applied: Optional[Dict[str, Any]] = Field(None, description="Filters that were applied")
    timestamp: Optional[str] = Field(None, description="Response timestamp (ISO format)")
