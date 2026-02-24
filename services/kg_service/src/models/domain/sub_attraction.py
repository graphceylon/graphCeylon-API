"""Models for sub-attraction (POI) data and operations.

Sub-attractions are individual Points of Interest within parent attraction locations.
Each parent attraction (e.g., Colombo, Kandy) contains multiple sub-attractions
such as temples, restaurants, shops, and viewpoints.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ========== Nested Models ==========

class POIContactInfo(BaseModel):
    """Contact information extracted from OSM tags."""
    phone: Optional[str] = Field(None, description="Local phone number")
    email: Optional[str] = Field(None, description="Email address")
    website: Optional[str] = Field(None, description="Website URL")


class POILocationInfo(BaseModel):
    """Location details extracted from OSM tags."""
    street: Optional[str] = Field(None, description="Street name")
    housenumber: Optional[str] = Field(None, description="House/building number")
    city: Optional[str] = Field(None, description="City name")


class POIReligionInfo(BaseModel):
    """Religious classification for places of worship."""
    religion: Optional[str] = Field(None, description="Religion (buddhist, hindu, muslim, etc.)")
    denomination: Optional[str] = Field(None, description="Denomination (mahayana, theravada, etc.)")


class POIFoodInfo(BaseModel):
    """Food-related details for restaurants and cafes."""
    cuisine: Optional[str] = Field(None, description="Cuisine type (chinese, coffee_shop, etc.)")
    takeaway: Optional[str] = Field(None, description="Takeaway availability")


class POIBusinessInfo(BaseModel):
    """Business/brand information."""
    brand: Optional[str] = Field(None, description="Brand name")
    brand_wikidata: Optional[str] = Field(None, description="Wikidata brand ID")
    operator: Optional[str] = Field(None, description="Operator name")


class POIAccessibilityInfo(BaseModel):
    """Accessibility information."""
    wheelchair: Optional[str] = Field(None, description="Wheelchair accessibility")


class POIEnrichedData(BaseModel):
    """Structured data enriched from OSM tags."""
    contact: Optional[POIContactInfo] = None
    location: Optional[POILocationInfo] = None
    religion: Optional[POIReligionInfo] = None
    food: Optional[POIFoodInfo] = None
    business: Optional[POIBusinessInfo] = None
    accessibility: Optional[POIAccessibilityInfo] = None


class POIReview(BaseModel):
    """Google Places review."""
    author: str = Field(..., description="Review author name")
    rating: int = Field(..., ge=1, le=5, description="Review rating (1-5)")
    text: str = Field(default="", description="Review text")
    time: int = Field(..., description="Unix timestamp of review")
    relative_time: str = Field(default="", description="Human-readable time (e.g., 'a month ago')")


class POIOpeningHoursPeriod(BaseModel):
    """Single opening hours period."""
    open: Dict[str, Any] = Field(..., description="Opening time {day, time}")
    close: Optional[Dict[str, Any]] = Field(None, description="Closing time {day, time}")


class POIOpeningHours(BaseModel):
    """Opening hours information from Google Places."""
    open_now: Optional[bool] = Field(None, description="Currently open")
    periods: List[POIOpeningHoursPeriod] = Field(default_factory=list)
    weekday_text: List[str] = Field(default_factory=list, description="Human-readable weekly schedule")


class POIAddressInfo(BaseModel):
    """Address information from Google Places."""
    formatted_address: Optional[str] = None
    administrative_areas: Optional[Dict[str, str]] = Field(
        default_factory=dict,
        description="Administrative areas (country, province, district, city, etc.)"
    )


class POIGoogleLinks(BaseModel):
    """Google Maps link collection."""
    google_maps_search: Optional[str] = None
    google_maps_coordinates: Optional[str] = None
    google_maps_directions: Optional[str] = None
    google_street_view: Optional[str] = None
    google_earth: Optional[str] = None
    google_maps_place: Optional[str] = None
    google_maps_cid: Optional[str] = None


class POIGoogleEnrichment(BaseModel):
    """Google Places enrichment data."""
    enriched_at: Optional[str] = Field(None, description="ISO datetime of enrichment")
    place_id: Optional[str] = Field(None, description="Google Place ID")
    rating: Optional[float] = Field(None, ge=0, le=5, description="Google rating (0-5)")
    user_ratings_total: Optional[int] = Field(None, ge=0, description="Total user ratings")
    price_level: Optional[int] = Field(None, ge=0, le=4, description="Price level (0-4)")
    photos: List[str] = Field(default_factory=list, description="Photo URLs (up to 5)")
    reviews: List[POIReview] = Field(default_factory=list, description="User reviews (up to 3)")
    website: Optional[str] = None
    phone: Optional[str] = Field(None, description="Local phone number")
    international_phone: Optional[str] = Field(None, description="International phone (+94 ...)")
    formatted_address: Optional[str] = None
    address_info: Optional[POIAddressInfo] = None
    opening_hours: Optional[Dict[str, Any]] = Field(default_factory=dict)
    business_status: Optional[str] = Field(None, description="OPERATIONAL, CLOSED_PERMANENTLY, etc.")
    google_maps_url: Optional[str] = None
    place_types: List[str] = Field(default_factory=list, description="Google place type taxonomy")
    editorial_summary: Optional[str] = None
    google_links: Optional[POIGoogleLinks] = None
    vicinity: Optional[str] = None
    icon: Optional[str] = None
    plus_code: Optional[str] = None


# ========== Core POI Model ==========

class SubAttractionPOI(BaseModel):
    """Single point of interest within a parent attraction location."""
    name: str = Field(..., description="POI name")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    tags: Dict[str, str] = Field(default_factory=dict, description="OSM tags")
    groups: List[str] = Field(default_factory=list, description="Category groups")
    enriched_data: Optional[POIEnrichedData] = Field(None, description="Structured enriched data")
    google_enrichment: Optional[POIGoogleEnrichment] = Field(None, description="Google Places data")


class SubAttractionFile(BaseModel):
    """Complete sub-attraction data file for a location."""
    location: str = Field(..., description="Parent attraction/location name")
    total_pois: int = Field(..., ge=0, description="Number of POIs in file")
    fetched_at: Optional[str] = Field(None, description="ISO datetime when data was fetched")
    pois: List[SubAttractionPOI] = Field(default_factory=list, description="List of POIs")
    google_enrichment_metadata: Optional[Dict[str, Any]] = Field(None, description="File-level enrichment stats")


# ========== Request Models ==========

class SubAttractionQueryRequest(BaseModel):
    """Request model for querying sub-attractions."""
    parent_attraction: Optional[str] = Field(None, description="Filter by parent attraction name")
    group: Optional[str] = Field(None, description="Filter by POI group (e.g., 'Shopping & City')")
    district: Optional[str] = Field(None, description="Filter by district")
    province: Optional[str] = Field(None, description="Filter by province")
    name: Optional[str] = Field(None, description="Search by POI name (partial match)")
    amenity_type: Optional[str] = Field(None, description="Filter by amenity type (restaurant, cafe, etc.)")
    min_rating: Optional[float] = Field(None, ge=0, le=5, description="Minimum Google rating")
    has_opening_hours: Optional[bool] = Field(None, description="Filter POIs with/without opening hours")
    limit: int = Field(20, ge=1, le=100, description="Maximum results")


class SubAttractionSearchRequest(BaseModel):
    """Request model for orchestrator sub-attraction search.

    Mirrors AttractionSearchRequest so the orchestrator can call both
    endpoints with the same payload shape.
    """
    city: Optional[str] = Field(None, description="City name (e.g., 'Kandy', 'Colombo', 'Galle'). Optional if poi_category is provided.")
    country: str = Field(default="Sri Lanka", description="Country name (e.g., 'Sri Lanka')")
    poi_name: Optional[str] = Field(None, description="Specific POI name to search for")
    poi_category: Optional[str] = Field(None, description="Category of POI (e.g., 'temple', 'museum', 'park')")
    days: Optional[int] = Field(None, description="Number of days for trip planning context")
    tags: Optional[List[str]] = Field(None, description="Tags for filtering (e.g., ['historical', 'cultural'])")
    user_id: Optional[str] = Field(None, description="User ID for personalization")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    query: Optional[str] = Field(None, description="Natural language query")


# ========== Response Models ==========

class SubAttractionItem(BaseModel):
    """Single sub-attraction in orchestrator search results.

    Field layout mirrors AttractionItem so the orchestrator can treat
    attraction and sub-attraction results uniformly.
    """
    name: str = Field(..., description="POI name")
    category: Optional[str] = Field(None, description="POI category/type")
    description: Optional[str] = Field(None, description="Brief description")
    location: Optional[str] = Field(None, description="Location/address")
    city: Optional[str] = Field(None, description="City name")
    district: Optional[str] = Field(None, description="District name")
    province: Optional[str] = Field(None, description="Province name")
    groups: Optional[List[str]] = Field(None, description="POI groups (e.g., 'Adventure & Hiking', 'Nature & Eco')")
    open_hours: Optional[str] = Field(None, description="Opening hours")
    entry_fee_lkr: Optional[str] = Field(None, description="Entry fee in LKR")
    source: str = Field(default="kg_service", description="Data source")
    rating: Optional[float] = Field(None, description="Google rating (0-5)")
    coordinates: Optional[str] = Field(None, description="Lat, Lon coordinates")
    website: Optional[str] = Field(None, description="Official website")
    phone: Optional[str] = Field(None, description="Phone number")


class SubAttractionResponse(BaseModel):
    """Response model for sub-attraction queries."""
    sub_attractions: List[Dict[str, Any]] = Field(..., description="List of sub-attractions")
    count: int = Field(..., description="Number of results returned")
    query_info: Optional[Dict[str, Any]] = Field(None, description="Query metadata")


class SubAttractionSearchResponse(BaseModel):
    """Response model for orchestrator sub-attraction search.

    Mirrors AttractionSearchResponse for uniform orchestrator handling.
    """
    ok: bool = Field(..., description="Whether search was successful")
    city: str = Field(..., description="City searched")
    country: str = Field(..., description="Country searched")
    items: List[SubAttractionItem] = Field(default_factory=list, description="List of sub-attractions")
    summary: str = Field(default="", description="Natural language summary of results")
    error: Optional[str] = Field(None, description="Error type if ok=False")
    details: Optional[str] = Field(None, description="Error details if ok=False")


class SubAttractionInitResponse(BaseModel):
    """Response model for sub-attraction initialization."""
    success: bool
    locations_processed: int = 0
    sub_attractions_created: int = 0
    groups_created: int = 0
    relationships_created: int = 0
    hotel_links_created: int = 0
    errors: List[str] = Field(default_factory=list)
    message: str = ""


class SubAttractionStatistics(BaseModel):
    """Statistics about sub-attraction data in the knowledge graph."""
    total_sub_attractions: int = 0
    total_parent_attractions: int = 0
    total_groups: int = 0
    by_group: Dict[str, int] = Field(default_factory=dict)
    by_parent: Dict[str, int] = Field(default_factory=dict)
    by_district: Dict[str, int] = Field(default_factory=dict)
    with_rating: int = 0
    with_website: int = 0
    with_opening_hours: int = 0
    average_rating: Optional[float] = None
    hotel_links: int = 0
