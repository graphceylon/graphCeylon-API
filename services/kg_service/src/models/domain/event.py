"""Models for event data and operations.

Events represent public happenings — concerts, exhibitions, conferences,
excursions, sports matches, etc. scraped from lankaevents.lk.

They sit under the "Event & Activity" domain in the knowledge graph.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ========== Data-Ingestion Models ==========


class EventImage(BaseModel):
    """Single image attached to an event."""
    image_id: Optional[str] = None
    filename: Optional[str] = None
    event_id: Optional[str] = None
    image_url: Optional[str] = None
    direct_url: Optional[str] = None


class EventRecord(BaseModel):
    """Raw event record as it appears in events.json."""
    event_id: str = Field(..., description="Unique event identifier from source")
    title: str = Field(..., description="Event title")
    event_type: str = Field(..., description="Event category")
    organizer: Optional[str] = Field(None, description="Organizer name")
    venue: Optional[str] = Field(None, description="Venue name / address")
    has_google_maps: Optional[bool] = Field(None)
    date_start: Optional[str] = Field(None, description="Human-readable start date")
    date_end: Optional[str] = Field(None, description="Human-readable end date")
    date_start_iso: Optional[str] = Field(None, description="ISO start date (YYYY-MM-DD)")
    date_end_iso: Optional[str] = Field(None, description="ISO end date (YYYY-MM-DD)")
    time_start: Optional[str] = Field(None, description="Start time (e.g. '07:00 pm')")
    time_end: Optional[str] = Field(None, description="End time (e.g. '11:59 pm')")
    description: Optional[str] = Field(None, description="Full description text")
    visibility: Optional[str] = Field(None, description="PUBLIC / PRIVATE")
    images: Optional[List[EventImage]] = Field(default_factory=list)
    page_images: Optional[List[str]] = Field(default_factory=list)
    hashtags: Optional[str] = Field(None, description="Hashtag string")
    calendar_days_appeared: Optional[List[int]] = Field(default_factory=list)
    event_detail_url: Optional[str] = None
    ical_link: Optional[str] = None
    google_calendar_link: Optional[str] = None


class EventFile(BaseModel):
    """Top-level structure of events.json."""
    metadata: Optional[Dict[str, Any]] = None
    events: List[EventRecord] = Field(default_factory=list)


# ========== Query / Response Models ==========


class EventQueryRequest(BaseModel):
    """Query request for events."""
    event_type: Optional[str] = Field(None, description="Filter by event type")
    venue: Optional[str] = Field(None, description="Filter by venue name")
    organizer: Optional[str] = Field(None, description="Filter by organizer")
    month: Optional[str] = Field(None, description="Filter by month name (e.g. 'January')")
    date_from: Optional[str] = Field(None, description="ISO date lower bound")
    date_to: Optional[str] = Field(None, description="ISO date upper bound")
    query: Optional[str] = Field(None, description="Free-text search on title/description")
    limit: int = Field(default=20, ge=1, le=100)


class EventResponse(BaseModel):
    """Generic response wrapping a list of events."""
    success: bool = True
    events: List[Dict[str, Any]] = Field(default_factory=list)
    count: int = 0
    message: Optional[str] = None


# ========== Orchestrator Contract (mirrors AttractionSearchRequest/Response) ==========


class EventSearchRequest(BaseModel):
    """Request model for event search from orchestrator.

    Uses the **same field names** as ``AttractionSearchRequest`` so that the
    centralized orchestrator can call this endpoint with the same payload.
    """
    city: Optional[str] = Field(None, description="City / venue location filter")
    country: str = Field(default="Sri Lanka", description="Country name")
    poi_name: Optional[str] = Field(None, description="Specific event name to search for")
    poi_category: Optional[str] = Field(None, description="Event type (e.g. 'Music/ Concert')")
    days: Optional[int] = Field(None, description="Number of days for trip planning context")
    tags: Optional[List[str]] = Field(None, description="Hashtag / keyword tags for filtering")
    user_id: Optional[str] = Field(None, description="User ID for personalization")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    query: Optional[str] = Field(None, description="Natural language query")


class EventItem(BaseModel):
    """Single event in orchestrator search results.

    Field names mirror ``AttractionItem`` for orchestrator compatibility.
    """
    name: str = Field(..., description="Event title")
    category: Optional[str] = Field(None, description="Event type")
    description: Optional[str] = Field(None, description="Brief description")
    location: Optional[str] = Field(None, description="Venue name / address")
    open_hours: Optional[str] = Field(None, description="Date range + time slot")
    entry_fee_lkr: Optional[str] = Field(None, description="Ticket / entry fee info")
    source: str = Field(default="kg_service", description="Data source")
    rating: Optional[float] = Field(None, description="Rating (not available for events)")
    coordinates: Optional[str] = Field(None, description="Lat, Lon (not available for events)")
    website: Optional[str] = Field(None, description="Event detail URL")
    phone: Optional[str] = Field(None, description="Contact phone (not available)")


class EventSearchResponse(BaseModel):
    """Response model for orchestrator event search.

    Mirrors ``AttractionSearchResponse`` exactly.
    """
    ok: bool = Field(..., description="Whether search was successful")
    city: str = Field(..., description="City searched")
    country: str = Field(..., description="Country searched")
    items: List[EventItem] = Field(default_factory=list, description="List of events")
    summary: str = Field(default="", description="Natural language summary of results")
    error: Optional[str] = Field(None, description="Error type if ok=False")
    details: Optional[str] = Field(None, description="Error details if ok=False")


# ========== Initialization Response ==========


class EventInitResponse(BaseModel):
    """Response from event initialization endpoint."""
    success: bool
    events_created: int = 0
    event_types_created: int = 0
    venues_created: int = 0
    organizers_created: int = 0
    relationships_created: int = 0
    errors: List[str] = Field(default_factory=list)
    message: str = ""


class EventStatistics(BaseModel):
    """Event knowledge-graph statistics."""
    total_events: int = 0
    total_event_types: int = 0
    total_venues: int = 0
    total_organizers: int = 0
    events_by_type: Dict[str, int] = Field(default_factory=dict)
    events_by_month: Dict[str, int] = Field(default_factory=dict)
