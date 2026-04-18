"""
Event Intelligence API endpoints.

Advanced AI-powered event discovery system with:
- Semantic search using vector embeddings
- Temporal pattern analysis
- Cross-domain recommendations (events + attractions)
- Graph-based event similarity
- Trend detection and insights

This is a separate, specialized API for advanced event intelligence features.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Query

from database.manager import DatabaseManager
from api.dependencies import get_db_manager
from models.domain.event_intelligence import (
    SemanticEventSearchRequest,
    SemanticSearchResponse,
    SimilarEventsRequest,
    SimilarEventsResponse,
    CrossDomainRecommendationRequest,
    CrossDomainRecommendationResponse,
    TemporalAnalysisRequest,
    TemporalAnalysisResponse,
    EmbeddingGenerationRequest,
    EmbeddingGenerationResponse,
    EmbeddingStatusResponse,
    EventIntelligenceError,
    EventIntelligenceItem,
    AttractionRecommendation,
)
from services.vector_embeddings import TemporalEventIntelligenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/event-intelligence", tags=["event-intelligence"])


# ------------------------------------------------------------------
# Semantic Search
# ------------------------------------------------------------------

@router.post(
    "/search/semantic",
    response_model=SemanticSearchResponse,
    summary="Semantic Event Search",
    description="""
    **Advanced semantic search using natural language queries.**
    
    Uses state-of-the-art 2026 AI technology:
    - 768-dimensional vector embeddings (sentence-transformers/all-mpnet-base-v2)
    - Temporal-aware embeddings capturing season, month, day-of-week
    - Context understanding (event vibe, audience, atmosphere)
    - Neo4j vector index for fast similarity search
    
    **Example Queries:**
    - "cultural events in Kandy with traditional music"
    - "family-friendly outdoor activities in Colombo"
    - "networking events for professionals this month"
    - "romantic evening events near Galle Fort"
    - "spiritual meditation retreats in hill country"
    
    **Returns:** Events ranked by semantic similarity with scores (0-1).
    """
)
def semantic_event_search(
    request: SemanticEventSearchRequest,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Semantic search for events using natural language queries."""
    try:
        logger.info(f"Semantic search: query='{request.query}', top_k={request.top_k}")
        
        service = TemporalEventIntelligenceService(db.driver)
        
        # Build filters
        filters = {}
        if request.event_type:
            filters["eventType"] = request.event_type
        if request.city:
            filters["city"] = request.city
        if request.date_from:
            filters["dateFrom"] = request.date_from
        if request.date_to:
            filters["dateTo"] = request.date_to
        
        # Perform semantic search
        results = service.semantic_search(
            query=request.query,
            top_k=request.top_k,
            filters=filters if filters else None
        )
        
        # Map to response model
        items = [EventIntelligenceItem(**result) for result in results]
        
        logger.info(f"Found {len(items)} events matching query")
        
        return SemanticSearchResponse(
            success=True,
            query=request.query,
            total_results=len(items),
            results=items,
            message=f"Found {len(items)} events matching your query"
        )
    
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=EventIntelligenceError(
                success=False,
                error="semantic_search_failed",
                details=str(e)
            ).model_dump()
        )


# ------------------------------------------------------------------
# Similar Events
# ------------------------------------------------------------------

@router.post(
    "/similarity/events",
    response_model=SimilarEventsResponse,
    summary="Find Similar Events",
    description="""
    **Find events similar to a given event using AI.**
    
    Combines multiple similarity signals:
    - **Vector Similarity (65%)**: Semantic similarity of content
    - **Graph Structure (35%)**: Shared venues, organizers
    - Event type matching
    - Temporal proximity
    
    **Use Cases:**
    - "More events like this one"
    - Event recommendation engines
    - Discovering event series or related happenings
    - Alternative event suggestions
    
    **Parameters:**
    - `use_graph=true`: Boosts events with same venue/organizer (+20% score)
    - `use_graph=false`: Pure semantic similarity
    """
)
def find_similar_events(
    request: SimilarEventsRequest,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Find events similar to a reference event."""
    try:
        logger.info(f"Finding similar events for: {request.event_id}")
        
        service = TemporalEventIntelligenceService(db.driver)
        
        results = service.find_similar_events(
            event_id=request.event_id,
            top_k=request.top_k,
            use_graph=request.use_graph
        )
        
        items = [EventIntelligenceItem(**result) for result in results]
        
        return SimilarEventsResponse(
            success=True,
            reference_event_id=request.event_id,
            similar_events=items,
            message=f"Found {len(items)} similar events"
        )
    
    except Exception as e:
        logger.error(f"Similar events search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=EventIntelligenceError(
                success=False,
                error="similar_events_failed",
                details=str(e)
            ).model_dump()
        )


# ------------------------------------------------------------------
# Cross-Domain Recommendations
# ------------------------------------------------------------------

@router.post(
    "/recommendations/attractions",
    response_model=CrossDomainRecommendationResponse,
    summary="Event + Attraction Recommendations",
    description="""
    **Cross-domain intelligent recommendations.**
    
    Recommends nearby attractions to visit around an event using:
    - Geographic proximity (same city/area)
    - Contextual relevance (complementary categories)
    - Quality ratings
    - Semantic similarity
    
    **Example Use Cases:**
    - "What attractions should I visit before/after this concert?"
    - "Plan a full day around this exhibition"
    - "Combine this sports event with nearby sightseeing"
    
    **Smart Pairing Logic:**
    - Music events → Entertainment venues, nightlife
    - Sports events → Outdoor attractions, recreation
    - Cultural events → Heritage sites, temples, museums
    - Exhibitions → Shopping, galleries, museums
    
    Perfect for **building complete itineraries** around events!
    """
)
def recommend_attractions_for_event(
    request: CrossDomainRecommendationRequest,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Recommend nearby attractions for an event."""
    try:
        logger.info(f"Getting attraction recommendations for event: {request.event_id}")
        
        service = TemporalEventIntelligenceService(db.driver)
        
        results = service.recommend_attractions_for_event(
            event_id=request.event_id,
            top_k=request.top_k
        )
        
        recommendations = [AttractionRecommendation(**result) for result in results]
        
        # Get event details for response
        event_title = None
        if results:
            cypher = "MATCH (e:Event {eventId: $eventId}) RETURN e.title AS title"
            with db.driver.session() as session:
                result = session.run(cypher, {"eventId": request.event_id})
                record = result.single()
                if record:
                    event_title = record["title"]
        
        return CrossDomainRecommendationResponse(
            success=True,
            event_id=request.event_id,
            event_title=event_title,
            recommended_attractions=recommendations,
            message=f"Found {len(recommendations)} nearby attractions"
        )
    
    except Exception as e:
        logger.error(f"Cross-domain recommendation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=EventIntelligenceError(
                success=False,
                error="recommendation_failed",
                details=str(e)
            ).model_dump()
        )


# ------------------------------------------------------------------
# Temporal Analytics
# ------------------------------------------------------------------

@router.post(
    "/analytics/temporal",
    response_model=TemporalAnalysisResponse,
    summary="Temporal Pattern Analysis",
    description="""
    **Analyze temporal patterns and trends in events.**
    
    Provides data-driven insights:
    - Monthly distribution of events
    - Seasonal trends (winter, spring, summer, autumn)
    - Busiest months and seasons
    - Event scheduling patterns
    
    **Use Cases:**
    - Tourism planning: "When is the best time to visit?"
    - Event organizers: "When should I schedule my event?"
    - Travel research: "What season has most cultural events?"
    - Market analysis: "Which months have highest event activity?"
    
    **Filter by event type** to analyze specific categories:
    - Music/Concert trends
    - Sports event seasons
    - Cultural event calendars
    - Exhibition scheduling patterns
    """
)
def analyze_temporal_patterns(
    request: TemporalAnalysisRequest,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Analyze temporal patterns in events."""
    try:
        logger.info(f"Temporal analysis: event_type={request.event_type}")
        
        service = TemporalEventIntelligenceService(db.driver)
        
        result = service.analyze_temporal_patterns(
            event_type=request.event_type
        )
        
        return TemporalAnalysisResponse(
            success=True,
            event_type_filter=request.event_type,
            **result,
            message=f"Analyzed {result['total_events_analyzed']} events"
        )
    
    except Exception as e:
        logger.error(f"Temporal analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=EventIntelligenceError(
                success=False,
                error="temporal_analysis_failed",
                details=str(e)
            ).model_dump()
        )


# ------------------------------------------------------------------
# Embedding Management
# ------------------------------------------------------------------

@router.post(
    "/embeddings/generate",
    response_model=EmbeddingGenerationResponse,
    summary="Generate Event Embeddings",
    description="""
    **Generate vector embeddings for all events in the database.**
    
    This endpoint:
    1. Fetches all events without embeddings (or all if force_regenerate=true)
    2. Generates 768-dimensional temporal-aware embeddings
    3. Stores embeddings in Neo4j Event nodes
    4. Processes in batches for efficiency
    
    **Embedding Features:**
    - Semantic content (title, description, type)
    - Temporal context (season, month, day-of-week)
    - Location context (venue, city)
    - Event vibe (cultural, party, educational, etc.)
    - Hashtags and keywords
    
    **Performance:**
    - Default batch size: 32 events
    - Processing time: ~10-30 seconds per batch
    - One-time setup required before using semantic search
    
    Run this once after adding new events or initializing the system.
    """
)
def generate_embeddings(
    request: EmbeddingGenerationRequest,
    db: DatabaseManager = Depends(get_db_manager),
):
    """Generate embeddings for all events."""
    try:
        logger.info(f"Starting embedding generation: batch_size={request.batch_size}, force={request.force_regenerate}")
        
        service = TemporalEventIntelligenceService(db.driver)
        
        result = service.generate_and_store_all_embeddings(
            batch_size=request.batch_size,
            force_regenerate=request.force_regenerate
        )
        
        return EmbeddingGenerationResponse(
            success=True,
            **result
        )
    
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=EventIntelligenceError(
                success=False,
                error="embedding_generation_failed",
                details=str(e)
            ).model_dump()
        )


@router.get(
    "/embeddings/status",
    response_model=EmbeddingStatusResponse,
    summary="Embedding Coverage Status",
    description="""
    **Check embedding coverage statistics.**
    
    Returns:
    - Total number of events in database
    - Number of events with embeddings
    - Number of events without embeddings
    - Coverage percentage
    - Model name and embedding dimensions
    
    Use this to verify that embeddings have been generated before using semantic search.
    Target: **100% coverage** for optimal search performance.
    """
)
def get_embedding_status(
    db: DatabaseManager = Depends(get_db_manager),
):
    """Get embedding coverage statistics."""
    try:
        service = TemporalEventIntelligenceService(db.driver)
        
        status = service.get_embedding_status()
        
        return EmbeddingStatusResponse(**status)
    
    except Exception as e:
        logger.error(f"Failed to get embedding status: {e}")
        raise HTTPException(
            status_code=500,
            detail=EventIntelligenceError(
                success=False,
                error="status_check_failed",
                details=str(e)
            ).model_dump()
        )


# ------------------------------------------------------------------
# Health Check
# ------------------------------------------------------------------

@router.get(
    "/health",
    summary="Event Intelligence Health Check",
    description="Check if the Event Intelligence service is operational."
)
def health_check(db: DatabaseManager = Depends(get_db_manager)):
    """Health check for event intelligence service."""
    try:
        # Check if Event nodes exist
        cypher = "MATCH (e:Event) RETURN count(e) AS count LIMIT 1"
        with db.driver.session() as session:
            result = session.run(cypher)
            record = result.single()
            event_count = record["count"] if record else 0
        
        return {
            "status": "healthy",
            "service": "Temporal Event Intelligence",
            "features": [
                "Semantic Search",
                "Event Similarity",
                "Cross-Domain Recommendations",
                "Temporal Analytics",
                "Graph-Based Insights"
            ],
            "events_in_database": event_count,
            "model": "sentence-transformers/all-mpnet-base-v2",
            "embedding_dimensions": 768
        }
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": str(e)
            }
        )
