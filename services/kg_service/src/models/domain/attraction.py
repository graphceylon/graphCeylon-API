"""Models for attraction data and operations."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# Import common geolocation models
from models.common import (
    CoordinatesModel,
    MapLinksModel,
    AdministrativeAreasModel,
    AddressInfoModel,
    GeocodingMetadataModel,
    GeolocationModel,
    GooglePlaceDataModel,
)


# Specific Models for Attractions

class LinkModel(BaseModel):
    """Link model for attraction links."""
    type: Optional[str] = Field(None, description="Link type (gallery, wikipedia, etc.)")
    url: Optional[str] = Field(None, description="URL")


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
