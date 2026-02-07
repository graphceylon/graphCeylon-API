"""Models for attraction data and operations."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class LinkModel(BaseModel):
    """Link model for attraction links."""
    type: Optional[str] = Field(None, description="Link type (gallery, wikipedia, etc.)")
    url: Optional[str] = Field(None, description="URL")


# Request Models

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


# ========== Orchestrator Models ==========

class AttractionSearchRequest(BaseModel):
    """Request model for attraction search from orchestrator."""
    city: str = Field(..., description="City name (e.g., 'Kandy', 'Colombo', 'Galle')")
    country: str = Field(..., description="Country name (e.g., 'Sri Lanka')")
    poi_name: Optional[str] = Field(None, description="Specific POI name to search for")
    poi_category: Optional[str] = Field(None, description="Category of POI (e.g., 'temple', 'museum', 'park')")
    days: Optional[int] = Field(None, description="Number of days for trip planning context")
    tags: Optional[List[str]] = Field(None, description="Tags for filtering (e.g., ['historical', 'cultural'])")
    user_id: Optional[str] = Field(None, description="User ID for personalization")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    query: Optional[str] = Field(None, description="Natural language query")


class AttractionItem(BaseModel):
    """Single attraction in orchestrator search results."""
    name: str = Field(..., description="Attraction name")
    category: Optional[str] = Field(None, description="Attraction category/type")
    description: Optional[str] = Field(None, description="Brief description")
    location: Optional[str] = Field(None, description="Location/address")
    open_hours: Optional[str] = Field(None, description="Opening hours")
    entry_fee_lkr: Optional[str] = Field(None, description="Entry fee in LKR")
    source: str = Field(default="kg_service", description="Data source")
    rating: Optional[float] = Field(None, description="Google rating (0-5)")
    coordinates: Optional[str] = Field(None, description="Lat, Lon coordinates")
    website: Optional[str] = Field(None, description="Official website")
    phone: Optional[str] = Field(None, description="Phone number")


class AttractionSearchResponse(BaseModel):
    """Response model for orchestrator attraction search."""
    ok: bool = Field(..., description="Whether search was successful")
    city: str = Field(..., description="City searched")
    country: str = Field(..., description="Country searched")
    items: List[AttractionItem] = Field(default_factory=list, description="List of attractions")
    summary: str = Field(default="", description="Natural language summary of results")
    error: Optional[str] = Field(None, description="Error type if ok=False")
    details: Optional[str] = Field(None, description="Error details if ok=False")
