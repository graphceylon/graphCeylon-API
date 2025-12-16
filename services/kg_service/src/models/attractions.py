"""Models for attraction data and operations."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# Nested Models

class CoordinatesModel(BaseModel):
    """Coordinates data."""
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")
    accuracy: Optional[str] = Field(None, description="Coordinate accuracy")


class MapLinksModel(BaseModel):
    """Map links for various services."""
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
    """Administrative area information."""
    country: Optional[str] = Field(None, description="Country name")
    country_code: Optional[str] = Field(None, description="Country code")
    province: Optional[str] = Field(None, description="Province/state name")
    district: Optional[str] = Field(None, description="District name")
    city: Optional[str] = Field(None, description="City name")
    town: Optional[str] = Field(None, description="Town name")
    village: Optional[str] = Field(None, description="Village name")
    postal_code: Optional[str] = Field(None, description="Postal code")
    route: Optional[str] = Field(None, description="Route/road name")
    street_number: Optional[str] = Field(None, description="Street number")


class AddressInfoModel(BaseModel):
    """Address information."""
    formatted_address: Optional[str] = Field(None, description="Formatted address string")
    administrative_areas: Optional[AdministrativeAreasModel] = Field(None, description="Administrative divisions")


class GeocodingMetadataModel(BaseModel):
    """Geocoding metadata."""
    geocoded_at: Optional[str] = Field(None, description="Geocoding timestamp")
    geocoding_service: Optional[str] = Field(None, description="Geocoding service used")
    geocoding_confidence: Optional[str] = Field(None, description="Geocoding confidence level")
    place_id: Optional[str] = Field(None, description="Place ID")


class GeolocationModel(BaseModel):
    """Complete geolocation data for attractions."""
    coordinates: Optional[CoordinatesModel] = Field(None, description="GPS coordinates")
    map_links: Optional[MapLinksModel] = Field(None, description="Map service links")
    address_info: Optional[AddressInfoModel] = Field(None, description="Address information")
    geocoding_metadata: Optional[GeocodingMetadataModel] = Field(None, description="Geocoding metadata")


class LinkModel(BaseModel):
    """Link model for attraction links."""
    type: Optional[str] = Field(None, description="Link type (gallery, wikipedia, etc.)")
    url: Optional[str] = Field(None, description="URL")


class GooglePlaceDataModel(BaseModel):
    """Google Places data for attractions."""
    rating: Optional[float] = Field(None, description="Google rating")
    user_ratings_total: Optional[int] = Field(None, description="Total number of ratings")
    reviews: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="User reviews")
    photos: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Photos")
    website: Optional[str] = Field(None, description="Website URL")
    phone_number: Optional[str] = Field(None, description="Phone number")
    opening_hours: Optional[Dict[str, Any]] = Field(None, description="Opening hours")
    price_level: Optional[int] = Field(None, description="Price level")
    place_types: Optional[List[str]] = Field(default_factory=list, description="Place types")
    place_url: Optional[str] = Field(None, description="Google Maps place URL")
    editorial_summary: Optional[str] = Field(None, description="Editorial summary")
    place_name: Optional[str] = Field(None, description="Place name")
    icon: Optional[str] = Field(None, description="Icon URL")
    vicinity: Optional[str] = Field(None, description="Vicinity description")


# Request Models

class AttractionModel(BaseModel):
    """Model for complete attraction data from JSON."""
    title: str = Field(..., description="Attraction name")
    description: Optional[str] = Field(None, description="Attraction description")
    image_url: Optional[str] = Field(None, description="Image URL")
    links: Optional[List[LinkModel]] = Field(default_factory=list, description="Related links")
    scraped_at: Optional[str] = Field(None, description="Scrape timestamp")
    geolocation: Optional[GeolocationModel] = Field(None, description="Complete geolocation data")
    google_place_data: Optional[GooglePlaceDataModel] = Field(None, description="Google Places data")


class CreateAttractionRequest(BaseModel):
    """Request model for creating an attraction."""
    title: str = Field(..., description="Attraction name")
    description: Optional[str] = Field(None, description="Attraction description")
    image_url: Optional[str] = Field(None, description="Image URL")
    district: Optional[str] = Field(None, description="District name to link attraction to")
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")
    google_place_id: Optional[str] = Field(None, description="Google Place ID")
    rating: Optional[float] = Field(None, description="Rating")
    formatted_address: Optional[str] = Field(None, description="Formatted address")
    website: Optional[str] = Field(None, description="Website URL")
    phone_number: Optional[str] = Field(None, description="Phone number")
    price_level: Optional[int] = Field(None, description="Price level")
    place_types: Optional[List[str]] = Field(default_factory=list, description="Place types")
    links: Optional[List[LinkModel]] = Field(default_factory=list, description="Related links")


class AttractionQueryRequest(BaseModel):
    """Request model for querying attractions."""
    district: Optional[str] = Field(None, description="Filter by district name")
    province: Optional[str] = Field(None, description="Filter by province name")
    title: Optional[str] = Field(None, description="Filter by attraction title")
    has_coordinates: Optional[bool] = Field(None, description="Filter attractions with/without coordinates")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")


# Response Models

class AttractionResponse(BaseModel):
    """Response model for attraction queries."""
    attractions: List[Dict[str, Any]] = Field(..., description="List of attractions")
    count: int = Field(..., description="Number of attractions returned")
    query_info: Optional[Dict[str, Any]] = Field(None, description="Query metadata")
