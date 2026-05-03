"""
Models for Temporal Event Intelligence API.

Advanced AI-powered event discovery and recommendation system.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ========== Request Models ==========


class SemanticEventSearchRequest(BaseModel):
    """Request for semantic event search using natural language."""
    query: str = Field(..., description="Natural language query (e.g., 'cultural events in Kandy')")
    top_k: int = Field(default=10, ge=1, le=50, description="Number of results to return")
    event_type: Optional[str] = Field(None, description="Filter by event type")
    city: Optional[str] = Field(None, description="Filter by city")
    date_from: Optional[str] = Field(None, description="Filter events from this date (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Filter events until this date (YYYY-MM-DD)")


class SimilarEventsRequest(BaseModel):
    """Request for finding similar events."""
    event_id: str = Field(..., description="Reference event ID")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of similar events to return")
    use_graph: bool = Field(default=True, description="Use graph structure (venues, organizers) in similarity")


class CrossDomainRecommendationRequest(BaseModel):
    """Request for cross-domain recommendations (events + attractions)."""
    event_id: str = Field(..., description="Event ID to get recommendations for")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of recommendations")


class TemporalAnalysisRequest(BaseModel):
    """Request for temporal pattern analysis."""
    event_type: Optional[str] = Field(None, description="Filter by event type (optional)")


class EmbeddingGenerationRequest(BaseModel):
    """Request for generating embeddings."""
    batch_size: int = Field(default=32, ge=1, le=100, description="Batch size for processing")
    force_regenerate: bool = Field(default=False, description="Regenerate embeddings even if they exist")


# ========== Response Models ==========


class EventIntelligenceItem(BaseModel):
    """Enhanced event item with AI-powered insights."""
    event_id: str = Field(..., alias="eventId")
    title: str
    description: Optional[str] = None
    event_type: Optional[str] = Field(None, alias="eventType")
    venue: Optional[str] = None
    organizer: Optional[str] = None
    date_start: Optional[str] = Field(None, alias="dateStart")
    date_end: Optional[str] = Field(None, alias="dateEnd")
    date_start_iso: Optional[str] = Field(None, alias="dateStartIso")
    time_start: Optional[str] = Field(None, alias="timeStart")
    time_end: Optional[str] = Field(None, alias="timeEnd")
    hashtags: Optional[str] = None
    event_detail_url: Optional[str] = Field(None, alias="eventDetailUrl")
    image_url: Optional[str] = Field(None, alias="imageUrl")
    
    # AI-powered fields
    similarity_score: Optional[float] = Field(None, alias="score", description="Semantic similarity score (0-1)")
    relevance_score: Optional[float] = Field(None, description="Relevance score (0-1)")
    
    class Config:
        populate_by_name = True


class SemanticSearchResponse(BaseModel):
    """Response for semantic event search."""
    success: bool = True
    query: str
    total_results: int
    results: List[EventIntelligenceItem]
    message: Optional[str] = None


class SimilarEventsResponse(BaseModel):
    """Response for similar events search."""
    success: bool = True
    reference_event_id: str
    similar_events: List[EventIntelligenceItem]
    message: Optional[str] = None


class AttractionRecommendation(BaseModel):
    """Recommended attraction for an event."""
    attraction_id: Optional[str] = Field(None, alias="attractionId")
    name: str
    description: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = None
    relevance_score: float
    
    class Config:
        populate_by_name = True


class CrossDomainRecommendationResponse(BaseModel):
    """Response for cross-domain recommendations."""
    success: bool = True
    event_id: str
    event_title: Optional[str] = None
    recommended_attractions: List[AttractionRecommendation]
    message: Optional[str] = None


class MonthlyDistribution(BaseModel):
    """Monthly event distribution."""
    month: str
    event_count: int


class TemporalAnalysisResponse(BaseModel):
    """Response for temporal pattern analysis."""
    success: bool = True
    monthly_distribution: List[MonthlyDistribution]
    seasonal_distribution: Dict[str, int]
    busiest_month: Optional[Dict[str, Any]] = None
    busiest_season: Optional[str] = None
    total_events_analyzed: int
    event_type_filter: Optional[str] = None
    message: Optional[str] = None


class EmbeddingStatusResponse(BaseModel):
    """Response for embedding coverage status."""
    total_events: int
    events_with_embeddings: int
    events_without_embeddings: int
    coverage_percentage: float
    model_name: str
    embedding_dimensions: int


class EmbeddingGenerationResponse(BaseModel):
    """Response for embedding generation."""
    success: bool = True
    total: int
    processed: int
    failed: int
    message: str


# ========== Error Response ==========


class EventIntelligenceError(BaseModel):
    """Error response for event intelligence API."""
    success: bool = False
    error: str
    details: Optional[str] = None
