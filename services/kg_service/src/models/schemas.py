"""Pydantic models for API request/response validation."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request model for querying provinces or districts, or raw Cypher queries."""
    province: Optional[str] = Field(None, description="Name of the province to query")
    district: Optional[str] = Field(None, description="Name of the district to query")
    query: Optional[str] = Field(None, description="Raw Cypher query to execute")


class ReasonRequest(BaseModel):
    """Request model for reasoning between provinces and districts."""
    start_province: Optional[str] = Field(None, description="Starting province name")
    target_district: Optional[str] = Field(None, description="Target district name")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Optional constraints for enhanced reasoning")


class PredictRequest(BaseModel):
    """Request model for similarity predictions."""
    name: str = Field(..., description="Name to find similar entities for")
    label: str = Field("District", description="Node label to search within")
    top_k: int = Field(5, ge=1, le=20, description="Number of similar results to return")


class ConstraintReasonRequest(BaseModel):
    """Request model for constraint-based reasoning."""
    constraints: Dict[str, Any] = Field(..., description="Constraints for filtering (e.g., {'province': 'Western', 'min_districts': 3})")


class WriteRequest(BaseModel):
    """Request model for writing/updating nodes."""
    node_type: str = Field(..., description="Type of node (Province, District, etc.)")
    properties: Dict[str, Any] = Field(..., description="Node properties")
    source: str = Field(..., description="Data source for provenance")


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Application version")


class QueryResponse(BaseModel):
    """Response model for query operations."""
    result: Optional[Dict[str, Any]] = Field(None, description="Structured query result data")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="Raw Cypher query results")
    execution_time: float = Field(..., description="Query execution time in milliseconds")
    provenance: Optional[Dict[str, Any]] = Field(None, description="Provenance metadata")


class ReasonResponse(BaseModel):
    """Response model for reasoning operations."""
    feasible: bool = Field(..., description="Whether the reasoning found a valid path")
    explanations: List[Dict[str, Any]] = Field(..., description="Reasoning explanations")
    result: Optional[Dict[str, Any]] = Field(None, description="Reasoning result if feasible")
    predictive: Optional[Dict[str, Any]] = Field(None, description="Predictive results if not feasible")
    provenance: Optional[Dict[str, Any]] = Field(None, description="Provenance metadata")


class PredictResponse(BaseModel):
    """Response model for prediction operations."""
    result: List[Dict[str, Any]] = Field(..., description="Similar entities with scores")
    explanation: Dict[str, Any] = Field(..., description="Explanation of prediction method")


class ConstraintReasonResponse(BaseModel):
    """Response model for constraint-based reasoning."""
    result: List[Dict[str, Any]] = Field(..., description="Filtered results")
    explanation: Dict[str, Any] = Field(..., description="Explanation of constraints applied")


class WriteResponse(BaseModel):
    """Response model for write operations."""
    success: bool = Field(..., description="Whether the write operation succeeded")
    node_id: Optional[int] = Field(None, description="ID of the created/updated node")
    provenance: Dict[str, Any] = Field(..., description="Provenance metadata")


class ValidationResponse(BaseModel):
    """Response model for SHACL validation."""
    conforms: bool = Field(..., description="Whether data conforms to SHACL shapes")
    violations: List[Dict[str, Any]] = Field(..., description="List of validation violations")


class ExportResponse(BaseModel):
    """Response model for data export."""
    turtle_like: List[Dict[str, Any]] = Field(..., description="Exported data in turtle-like format")


class ExplainResponse(BaseModel):
    """Response model for evidence explanation."""
    evidence: Dict[str, Any] = Field(..., description="Evidence path data")


class StatisticsResponse(BaseModel):
    """Response model for database statistics."""
    statistics: Dict[str, Any] = Field(..., description="Database statistics")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


# Attraction-related models
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


class AttractionResponse(BaseModel):
    """Response model for attraction queries."""
    attractions: List[Dict[str, Any]] = Field(..., description="List of attractions")
    count: int = Field(..., description="Number of attractions returned")
    query_info: Optional[Dict[str, Any]] = Field(None, description="Query metadata")


# Holiday-related models
class HolidayModel(BaseModel):
    """Model for holiday data."""
    id: str = Field(..., description="Unique holiday identifier")
    name: str = Field(..., description="Holiday name")
    description: Optional[str] = Field(None, description="Holiday description")
    start_date: str = Field(..., description="Start date (ISO format)")
    end_date: str = Field(..., description="End date (ISO format)")
    duration_days: int = Field(..., description="Duration in days")
    holiday_type: str = Field(..., description="Type of holiday (Poya Day, Public Holiday, etc.)")
    category: str = Field(..., description="Category (Religious, Cultural, National, General)")
    country: str = Field(..., description="Country name")
    country_code: str = Field(..., description="Country code")
    status: str = Field(..., description="Status (confirmed, tentative, etc.)")
    is_public_holiday: bool = Field(..., description="Whether it's a public holiday")
    location: Optional[str] = Field(None, description="Specific location if applicable")
    year: int = Field(..., description="Year")
    month: int = Field(..., description="Month (1-12)")
    day: int = Field(..., description="Day of month")
    weekday: str = Field(..., description="Day of week")
    calendar_link: Optional[str] = Field(None, description="Calendar event link")


class CreateHolidayRequest(BaseModel):
    """Request model for creating a holiday."""
    name: str = Field(..., description="Holiday name")
    description: Optional[str] = Field(None, description="Holiday description")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    holiday_type: str = Field(..., description="Type of holiday")
    category: str = Field(..., description="Category (Religious, Cultural, National, General)")
    is_public_holiday: bool = Field(True, description="Whether it's a public holiday")
    location: Optional[str] = Field(None, description="Specific location if applicable")


class HolidayQueryRequest(BaseModel):
    """Request model for querying holidays."""
    year: Optional[int] = Field(None, description="Filter by year")
    month: Optional[int] = Field(None, ge=1, le=12, description="Filter by month (1-12)")
    category: Optional[str] = Field(None, description="Filter by category")
    holiday_type: Optional[str] = Field(None, description="Filter by holiday type")
    is_public_holiday: Optional[bool] = Field(None, description="Filter by public holiday status")
    name: Optional[str] = Field(None, description="Search by holiday name")
    limit: int = Field(50, ge=1, le=200, description="Maximum number of results")


class HolidayResponse(BaseModel):
    """Response model for holiday queries."""
    holidays: List[Dict[str, Any]] = Field(..., description="List of holidays")
    count: int = Field(..., description="Number of holidays returned")
    query_info: Optional[Dict[str, Any]] = Field(None, description="Query metadata")


class TemporalStructureResponse(BaseModel):
    """Response model for temporal structure queries."""
    structure: Dict[str, Any] = Field(..., description="Temporal structure data")
    summary: Optional[Dict[str, Any]] = Field(None, description="Summary statistics")


# Tourism Project-related models
class ProjectDetailModel(BaseModel):
    """Model for project detail items."""
    key: Optional[str] = Field(None, description="Detail key")
    value: Optional[str] = Field(None, description="Detail value")


class TourismProjectModel(BaseModel):
    """Model for tourism project data."""
    title: str = Field(..., description="Project title")
    image: Optional[str] = Field(None, description="Project image URL")
    description: Optional[str] = Field(None, description="Project description")
    details: Optional[List[str]] = Field(default_factory=list, description="Project details")
    contact_text: Optional[str] = Field(None, description="Contact information")
    href: Optional[str] = Field(None, description="Project page link")


class CreateProjectRequest(BaseModel):
    """Request model for creating a tourism project."""
    title: str = Field(..., description="Project title")
    image: Optional[str] = Field(None, description="Project image URL")
    description: Optional[str] = Field(None, description="Project description")
    details: Optional[List[str]] = Field(default_factory=list, description="Project details")
    contact_text: Optional[str] = Field(None, description="Contact information")
    href: Optional[str] = Field(None, description="Project page link")
    province: Optional[str] = Field(None, description="Province name to link project to")
    district: Optional[str] = Field(None, description="District name to link project to")
    project_type: Optional[str] = Field(None, description="Type of project (Infrastructure, Regional, etc.)")


class ProjectQueryRequest(BaseModel):
    """Request model for querying tourism projects."""
    title: Optional[str] = Field(None, description="Search by project title")
    province: Optional[str] = Field(None, description="Filter by province")
    district: Optional[str] = Field(None, description="Filter by district")
    project_type: Optional[str] = Field(None, description="Filter by project type")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of results")


class ProjectResponse(BaseModel):
    """Response model for project queries."""
    projects: List[Dict[str, Any]] = Field(..., description="List of projects")
    count: int = Field(..., description="Number of projects returned")
    query_info: Optional[Dict[str, Any]] = Field(None, description="Query metadata")


# Tourism News-related models
class NewsArticleModel(BaseModel):
    """Model for news article data."""
    title: str = Field(..., description="Article title")
    date: Optional[str] = Field(None, description="Publication date")
    image_url: Optional[str] = Field(None, description="Article image URL")
    content: Optional[str] = Field(None, description="Article content/summary")
    read_more_url: Optional[str] = Field(None, description="Full article URL")
    scraped_at: Optional[str] = Field(None, description="Scrape timestamp")


class CreateNewsRequest(BaseModel):
    """Request model for creating a news article."""
    title: str = Field(..., description="Article title")
    date: Optional[str] = Field(None, description="Publication date (YYYY-MM-DD)")
    image_url: Optional[str] = Field(None, description="Article image URL")
    content: Optional[str] = Field(None, description="Article content/summary")
    read_more_url: Optional[str] = Field(None, description="Full article URL")
    category: Optional[str] = Field(None, description="News category")
    tags: Optional[List[str]] = Field(default_factory=list, description="Article tags")


class NewsQueryRequest(BaseModel):
    """Request model for querying news articles."""
    title: Optional[str] = Field(None, description="Search by article title")
    category: Optional[str] = Field(None, description="Filter by category")
    date_from: Optional[str] = Field(None, description="Filter articles from this date (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Filter articles to this date (YYYY-MM-DD)")
    year: Optional[int] = Field(None, description="Filter by year")
    month: Optional[int] = Field(None, ge=1, le=12, description="Filter by month (1-12)")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of results")


class NewsResponse(BaseModel):
    """Response model for news queries."""
    articles: List[Dict[str, Any]] = Field(..., description="List of news articles")
    count: int = Field(..., description="Number of articles returned")
    query_info: Optional[Dict[str, Any]] = Field(None, description="Query metadata")
