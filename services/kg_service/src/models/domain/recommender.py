"""Models for the Recommender service — route-based attraction discovery."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ========== Request ==========

class AttractionsOnRouteRequest(BaseModel):
    """Request body for the attractions-on-route recommender endpoint."""

    country: str = Field(default="Sri Lanka", description="Country scope")
    origin_city: str = Field(..., description="Starting city of the route")
    destination_city: str = Field(..., description="Ending city of the route")
    corridor_km: float = Field(
        default=5.0,
        ge=0.5,
        le=50.0,
        description="Search radius (km) around each sampled route point",
    )
    limit: int = Field(
        default=80,
        ge=1,
        le=500,
        description="Maximum total sub-attractions to return",
    )
    sampled_route_points: List[List[float]] = Field(
        ...,
        min_length=2,
        description="Ordered list of [lat, lon] waypoints along the route",
    )


# ========== Response ==========

class RouteSubAttractionItem(BaseModel):
    """A single sub-attraction discovered along the route."""

    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    parent_location: Optional[str] = None
    category: Optional[str] = None
    groups: Optional[List[str]] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    formatted_address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    province: Optional[str] = None
    editorial_summary: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    google_maps_url: Optional[str] = None
    opening_hours: Optional[List[str]] = None
    photos: Optional[List[str]] = None
    business_status: Optional[str] = None
    cuisine: Optional[str] = None
    religion: Optional[str] = None
    distance_km: Optional[float] = None


class RoutePointResult(BaseModel):
    """Sub-attractions found near a single route waypoint."""

    route_point: List[float] = Field(
        ..., description="The [lat, lon] coordinate this group belongs to"
    )
    route_point_index: int = Field(
        ..., description="0-based index of this point in the request"
    )
    sub_attractions: List[RouteSubAttractionItem] = Field(default_factory=list)
    count: int = Field(default=0, description="Number of sub-attractions at this point")


class AttractionsOnRouteResponse(BaseModel):
    """Response for the attractions-on-route recommender endpoint."""

    status: str = Field(default="ok")
    items: List[RoutePointResult] = Field(default_factory=list)
    debug: Dict[str, Any] = Field(default_factory=dict)
