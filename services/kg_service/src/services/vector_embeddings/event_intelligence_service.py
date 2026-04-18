"""
Temporal Event Intelligence Service

Advanced AI system for event discovery using:
- Semantic vector embeddings with temporal awareness
- Graph-based similarity and clustering
- Cross-domain recommendations (events ↔ attractions ↔ hotels)
- Temporal pattern recognition
- Contextual "vibe" understanding

State-of-the-art 2026 features for tourism recommendation.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

import numpy as np
from sentence_transformers import SentenceTransformer
from neo4j import Driver

logger = logging.getLogger(__name__)


class EventVibe(str, Enum):
    """Event vibe/atmosphere categories for contextual understanding."""
    CULTURAL = "cultural"
    PARTY = "party"
    EDUCATIONAL = "educational"
    SPIRITUAL = "spiritual"
    SPORTS = "sports"
    FAMILY = "family"
    ROMANTIC = "romantic"
    ADVENTURE = "adventure"
    NETWORKING = "networking"
    ARTISTIC = "artistic"


class EventAudienceType(str, Enum):
    """Target audience classification."""
    FAMILIES = "families"
    COUPLES = "couples"
    SOLO_TRAVELERS = "solo_travelers"
    STUDENTS = "students"
    PROFESSIONALS = "professionals"
    SENIORS = "seniors"
    YOUTH = "youth"
    ALL = "all"


class TemporalEventIntelligenceService:
    """
    Advanced AI service for intelligent event discovery and recommendations.
    
    Features:
    - Temporal-aware vector embeddings (768 dimensions)
    - Semantic similarity search
    - Graph-based event clustering
    - Cross-domain recommendations
    - Trend analysis and pattern recognition
    - Context understanding (vibe, audience, best time to visit)
    """

    def __init__(
        self,
        driver: Driver,
        model_name: str = "sentence-transformers/all-mpnet-base-v2",
        device: str = "cpu"
    ):
        """
        Initialize the Event Intelligence Service.
        
        Args:
            driver: Neo4j driver instance
            model_name: Sentence transformer model (768-dim embeddings)
            device: Compute device ('cpu' or 'cuda')
        """
        self.driver = driver
        self.model_name = model_name
        self.device = device
        self.model = None
        self._vibe_keywords = self._init_vibe_keywords()
        self._audience_keywords = self._init_audience_keywords()
        
        logger.info(f"Initializing TemporalEventIntelligenceService with model: {model_name}")
    
    def _load_model(self):
        """Lazy load the sentence transformer model."""
        if self.model is None:
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.info("Model loaded successfully")
    
    # ============================================================
    # CORE: Temporal-Aware Embedding Generation
    # ============================================================
    
    def generate_embedding(self, event_data: Dict[str, Any]) -> np.ndarray:
        """
        Generate temporal-aware embedding for an event.
        
        Creates rich semantic representation including:
        - Title and description
        - Event type and category
        - Venue and location context
        - Temporal features (season, month, day-of-week)
        - Hashtags and keywords
        - Organizer context
        
        Args:
            event_data: Event dictionary from Neo4j
        
        Returns:
            768-dimensional embedding vector
        """
        self._load_model()
        
        # Build comprehensive text representation
        text = self._build_temporal_embedding_text(event_data)
        
        # Generate embedding
        embedding = self.model.encode(text, convert_to_numpy=True)
        
        return embedding
    
    def _build_temporal_embedding_text(self, event: Dict[str, Any]) -> str:
        """
        Build rich text representation with temporal context.
        
        Format:
        {title}. {description}. Event type: {eventType}. 
        Venue: {venue}. Organized by: {organizer}.
        Season: {season}. Month: {month}. Day: {dayOfWeek}.
        Tags: {hashtags}. Context: {vibe_context}.
        """
        parts = []
        
        # Core content
        if event.get("title"):
            parts.append(event["title"])
        
        if event.get("description"):
            desc = event["description"]
            # Truncate very long descriptions
            if len(desc) > 500:
                desc = desc[:497] + "..."
            parts.append(desc)
        
        # Event type
        if event.get("eventType"):
            parts.append(f"Event type: {event['eventType']}")
        
        # Location context
        if event.get("venue"):
            parts.append(f"Venue: {event['venue']}")
        
        # Organizer context
        if event.get("organizer"):
            parts.append(f"Organized by: {event['organizer']}")
        
        # Temporal context
        temporal_context = self._extract_temporal_context(event)
        if temporal_context:
            parts.append(temporal_context)
        
        # Hashtags and keywords
        if event.get("hashtags"):
            hashtags = event["hashtags"].replace("#", "").replace("_", " ")
            parts.append(f"Tags: {hashtags}")
        
        # Vibe/context understanding
        vibe_context = self._infer_event_vibe(event)
        if vibe_context:
            parts.append(f"Context: {vibe_context}")
        
        return ". ".join(parts)
    
    def _extract_temporal_context(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract temporal features: season, month, day-of-week."""
        date_str = event.get("dateStartIso")
        if not date_str:
            return None
        
        try:
            date = datetime.fromisoformat(date_str)
            
            # Season
            month = date.month
            if month in [12, 1, 2]:
                season = "winter"
            elif month in [3, 4, 5]:
                season = "spring"
            elif month in [6, 7, 8]:
                season = "summer"
            else:
                season = "autumn"
            
            # Month name
            month_name = date.strftime("%B")
            
            # Day of week
            day_name = date.strftime("%A")
            
            return f"Season: {season}. Month: {month_name}. Day: {day_name}"
        
        except Exception as e:
            logger.warning(f"Failed to parse date {date_str}: {e}")
            return None
    
    def _infer_event_vibe(self, event: Dict[str, Any]) -> str:
        """
        Infer event vibe/atmosphere from title, description, and type.
        
        Returns comma-separated vibe keywords.
        """
        text = " ".join([
            event.get("title", ""),
            event.get("description", ""),
            event.get("eventType", ""),
            event.get("hashtags", "")
        ]).lower()
        
        detected_vibes = []
        for vibe, keywords in self._vibe_keywords.items():
            if any(keyword in text for keyword in keywords):
                detected_vibes.append(vibe.value)
        
        return ", ".join(detected_vibes) if detected_vibes else "general"
    
    def _init_vibe_keywords(self) -> Dict[EventVibe, List[str]]:
        """Initialize keywords for vibe detection."""
        return {
            EventVibe.CULTURAL: [
                "culture", "cultural", "heritage", "traditional", "folk",
                "history", "museum", "exhibition", "art", "gallery"
            ],
            EventVibe.PARTY: [
                "party", "dj", "nightclub", "dance", "music festival",
                "concert", "night", "celebration", "fest"
            ],
            EventVibe.EDUCATIONAL: [
                "workshop", "seminar", "conference", "lecture", "training",
                "course", "learning", "education", "symposium", "summit"
            ],
            EventVibe.SPIRITUAL: [
                "spiritual", "meditation", "yoga", "temple", "religious",
                "buddhist", "hindu", "church", "pilgrimage", "dharma"
            ],
            EventVibe.SPORTS: [
                "sports", "match", "game", "tournament", "championship",
                "cricket", "rugby", "football", "marathon", "race"
            ],
            EventVibe.FAMILY: [
                "family", "kids", "children", "carnival", "fair",
                "amusement", "zoo", "park", "playground"
            ],
            EventVibe.ROMANTIC: [
                "romantic", "couples", "valentine", "date", "intimate",
                "candlelight", "dinner show"
            ],
            EventVibe.ADVENTURE: [
                "adventure", "outdoor", "hiking", "safari", "camping",
                "extreme", "trekking", "exploration"
            ],
            EventVibe.NETWORKING: [
                "networking", "business", "professional", "career",
                "meetup", "expo", "trade show", "b2b"
            ],
            EventVibe.ARTISTIC: [
                "theater", "performance", "drama", "opera", "ballet",
                "artistic", "creative", "poetry", "literature"
            ]
        }
    
    def _init_audience_keywords(self) -> Dict[EventAudienceType, List[str]]:
        """Initialize keywords for audience detection."""
        return {
            EventAudienceType.FAMILIES: [
                "family", "kids", "children", "all ages", "family-friendly"
            ],
            EventAudienceType.COUPLES: [
                "couples", "romantic", "date night", "valentine"
            ],
            EventAudienceType.SOLO_TRAVELERS: [
                "solo", "backpacker", "individual", "traveler"
            ],
            EventAudienceType.STUDENTS: [
                "student", "university", "college", "youth", "academic"
            ],
            EventAudienceType.PROFESSIONALS: [
                "professional", "business", "corporate", "executive"
            ],
            EventAudienceType.SENIORS: [
                "seniors", "elderly", "retirees", "50+"
            ],
            EventAudienceType.YOUTH: [
                "youth", "teen", "young", "18-25"
            ]
        }
    
    # ============================================================
    # STORAGE: Store embeddings in Neo4j
    # ============================================================
    
    def store_embedding(self, event_id: str, embedding: np.ndarray) -> bool:
        """
        Store embedding vector in Neo4j Event node.
        
        Args:
            event_id: Event ID
            embedding: 768-dimensional vector
        
        Returns:
            True if successful
        """
        try:
            embedding_list = embedding.tolist()
            
            cypher = """
            MATCH (e:Event {eventId: $eventId})
            SET e.embedding = $embedding,
                e.embeddingGeneratedAt = datetime()
            RETURN e.eventId AS eventId
            """
            
            with self.driver.session() as session:
                result = session.run(cypher, {
                    "eventId": event_id,
                    "embedding": embedding_list
                })
                
                if result.single():
                    logger.debug(f"Stored embedding for event: {event_id}")
                    return True
                else:
                    logger.warning(f"Event not found: {event_id}")
                    return False
        
        except Exception as e:
            logger.error(f"Failed to store embedding for {event_id}: {e}")
            return False
    
    def generate_and_store_all_embeddings(
        self,
        batch_size: int = 32,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate and store embeddings for all events in the database.
        
        Args:
            batch_size: Number of events to process in each batch
            force_regenerate: If True, regenerate embeddings even if they exist
        
        Returns:
            Statistics dictionary
        """
        self._load_model()
        
        # Fetch events needing embeddings
        cypher = """
        MATCH (e:Event)
        WHERE $force OR e.embedding IS NULL
        RETURN e.eventId AS eventId,
               e.title AS title,
               e.description AS description,
               e.eventType AS eventType,
               e.venue AS venue,
               e.organizer AS organizer,
               e.dateStartIso AS dateStartIso,
               e.hashtags AS hashtags
        """
        
        with self.driver.session() as session:
            result = session.run(cypher, {"force": force_regenerate})
            events = [record.data() for record in result]
        
        if not events:
            logger.info("No events need embeddings")
            return {
                "total": 0,
                "processed": 0,
                "failed": 0,
                "message": "All events already have embeddings"
            }
        
        logger.info(f"Processing {len(events)} events in batches of {batch_size}")
        
        processed = 0
        failed = 0
        
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} events)")
            
            for event in batch:
                try:
                    embedding = self.generate_embedding(event)
                    success = self.store_embedding(event["eventId"], embedding)
                    
                    if success:
                        processed += 1
                    else:
                        failed += 1
                
                except Exception as e:
                    logger.error(f"Failed to process event {event['eventId']}: {e}")
                    failed += 1
        
        logger.info(f"Embedding generation complete: {processed} processed, {failed} failed")
        
        return {
            "total": len(events),
            "processed": processed,
            "failed": failed,
            "message": f"Successfully processed {processed}/{len(events)} events"
        }
    
    # ============================================================
    # SEARCH: Semantic vector search
    # ============================================================
    
    def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search using vector similarity.
        
        Args:
            query: Natural language search query
            top_k: Number of results to return
            filters: Optional filters (eventType, city, dateRange)
        
        Returns:
            List of events with similarity scores
        """
        self._load_model()
        
        # Generate query embedding
        query_embedding = self.model.encode(query, convert_to_numpy=True)
        
        # Build filter clause
        filter_clause = "WHERE e.embedding IS NOT NULL"
        params = {
            "queryEmbedding": query_embedding.tolist(),
            "topK": top_k
        }
        
        if filters:
            if filters.get("eventType"):
                filter_clause += " AND toLower(e.eventType) CONTAINS toLower($eventType)"
                params["eventType"] = filters["eventType"]
            
            if filters.get("city"):
                filter_clause += " AND (toLower(e.venue) CONTAINS toLower($city) OR toLower(e.title) CONTAINS toLower($city))"
                params["city"] = filters["city"]
            
            if filters.get("dateFrom"):
                filter_clause += " AND e.dateStartIso >= $dateFrom"
                params["dateFrom"] = filters["dateFrom"]
            
            if filters.get("dateTo"):
                filter_clause += " AND e.dateEndIso <= $dateTo"
                params["dateTo"] = filters["dateTo"]
        
        # Vector similarity search using Neo4j vector index
        cypher = f"""
        CALL db.index.vector.queryNodes('event_embeddings', $topK, $queryEmbedding)
        YIELD node AS e, score
        {filter_clause}
        RETURN e.eventId AS eventId,
               e.title AS title,
               e.description AS description,
               e.eventType AS eventType,
               e.venue AS venue,
               e.organizer AS organizer,
               e.dateStart AS dateStart,
               e.dateEnd AS dateEnd,
               e.dateStartIso AS dateStartIso,
               e.timeStart AS timeStart,
               e.timeEnd AS timeEnd,
               e.hashtags AS hashtags,
               e.eventDetailUrl AS eventDetailUrl,
               score
        ORDER BY score DESC
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(cypher, params)
                return [record.data() for record in result]
        
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            # Fallback to cosine similarity if vector index not available
            return self._fallback_similarity_search(query_embedding, top_k, filters)
    
    def _fallback_similarity_search(
        self,
        query_embedding: np.ndarray,
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Fallback similarity search using manual cosine similarity.
        Used when vector index is not available.
        """
        logger.info("Using fallback similarity search")
        
        # Fetch all events with embeddings
        filter_clause = "WHERE e.embedding IS NOT NULL"
        params = {"topK": top_k}
        
        if filters:
            if filters.get("eventType"):
                filter_clause += " AND toLower(e.eventType) CONTAINS toLower($eventType)"
                params["eventType"] = filters["eventType"]
            
            if filters.get("city"):
                filter_clause += " AND (toLower(e.venue) CONTAINS toLower($city) OR toLower(e.title) CONTAINS toLower($city))"
                params["city"] = filters["city"]
        
        cypher = f"""
        MATCH (e:Event)
        {filter_clause}
        RETURN e.eventId AS eventId,
               e.title AS title,
               e.description AS description,
               e.eventType AS eventType,
               e.venue AS venue,
               e.organizer AS organizer,
               e.dateStart AS dateStart,
               e.dateEnd AS dateEnd,
               e.dateStartIso AS dateStartIso,
               e.hashtags AS hashtags,
               e.embedding AS embedding
        """
        
        with self.driver.session() as session:
            result = session.run(cypher, params)
            events = [record.data() for record in result]
        
        # Calculate cosine similarity
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        
        for event in events:
            embedding = np.array(event["embedding"])
            embedding_norm = embedding / np.linalg.norm(embedding)
            similarity = np.dot(query_norm, embedding_norm)
            event["score"] = float(similarity)
            del event["embedding"]  # Remove large embedding array
        
        # Sort by similarity and return top_k
        events.sort(key=lambda x: x["score"], reverse=True)
        return events[:top_k]
    
    # ============================================================
    # CROSS-DOMAIN: Event + Attraction Recommendations
    # ============================================================
    
    def recommend_attractions_for_event(
        self,
        event_id: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recommend nearby attractions for an event using location and context.
        
        Args:
            event_id: Event ID
            top_k: Number of attractions to recommend
        
        Returns:
            List of recommended attractions
        """
        # Get event details
        cypher_event = """
        MATCH (e:Event {eventId: $eventId})
        RETURN e.eventId AS eventId,
               e.title AS title,
               e.venue AS venue,
               e.eventType AS eventType,
               e.embedding AS embedding
        """
        
        with self.driver.session() as session:
            result = session.run(cypher_event, {"eventId": event_id})
            event = result.single()
            
            if not event:
                logger.warning(f"Event not found: {event_id}")
                return []
            
            event_data = event.data()
        
        # Extract city from venue
        venue = event_data.get("venue", "")
        city_match = self._extract_city_from_venue(venue)
        
        # Find nearby attractions
        cypher_attractions = """
        MATCH (a:Attraction)
        WHERE toLower(a.city) CONTAINS toLower($city)
           OR toLower(a.name) CONTAINS toLower($city)
        OPTIONAL MATCH (a)-[:BELONGS_TO]->(c:Category)
        RETURN a.attractionId AS attractionId,
               a.name AS name,
               a.description AS description,
               a.city AS city,
               a.rating AS rating,
               c.name AS category
        LIMIT $topK
        """
        
        with self.driver.session() as session:
            result = session.run(cypher_attractions, {
                "city": city_match or "Colombo",
                "topK": top_k * 2  # Get more to filter
            })
            attractions = [record.data() for record in result]
        
        # If event has embedding, rank by semantic similarity
        if event_data.get("embedding") and attractions:
            event_embedding = np.array(event_data["embedding"])
            
            # For attractions without embeddings, use simple scoring
            for attr in attractions:
                attr["relevance_score"] = self._calculate_attraction_relevance(
                    event_data, attr
                )
            
            attractions.sort(key=lambda x: x["relevance_score"], reverse=True)
            return attractions[:top_k]
        
        return attractions[:top_k]
    
    def _extract_city_from_venue(self, venue: str) -> Optional[str]:
        """Extract city name from venue string."""
        if not venue:
            return None
        
        # Common Sri Lankan cities
        cities = [
            "Colombo", "Kandy", "Galle", "Jaffna", "Negombo",
            "Trincomalee", "Anuradhapura", "Polonnaruwa", "Sigiriya",
            "Ella", "Nuwara Eliya", "Bentota", "Hikkaduwa", "Batticaloa"
        ]
        
        venue_lower = venue.lower()
        for city in cities:
            if city.lower() in venue_lower:
                return city
        
        return None
    
    def _calculate_attraction_relevance(
        self,
        event: Dict[str, Any],
        attraction: Dict[str, Any]
    ) -> float:
        """
        Calculate relevance score between event and attraction.
        
        Uses heuristics:
        - Same city: +0.3
        - High rating: +0.2
        - Complementary categories: +0.3
        """
        score = 0.0
        
        # Same city bonus
        event_venue = event.get("venue", "").lower()
        attr_city = attraction.get("city", "").lower()
        if attr_city and attr_city in event_venue:
            score += 0.3
        
        # Rating bonus
        rating = attraction.get("rating")
        if rating:
            score += min(rating / 5.0 * 0.2, 0.2)
        
        # Category complementarity
        event_type = event.get("eventType", "").lower()
        attr_category = attraction.get("category", "").lower()
        
        complementary_pairs = {
            "music": ["entertainment", "nightlife"],
            "sports": ["outdoor", "recreation"],
            "cultural": ["heritage", "museum", "temple"],
            "exhibition": ["museum", "gallery", "shopping"],
        }
        
        for event_key, attr_keys in complementary_pairs.items():
            if event_key in event_type:
                if any(key in attr_category for key in attr_keys):
                    score += 0.3
                    break
        
        return score
    
    # ============================================================
    # GRAPH ANALYTICS: Event clustering and similarity
    # ============================================================
    
    def find_similar_events(
        self,
        event_id: str,
        top_k: int = 5,
        use_graph: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find similar events using vector similarity and graph structure.
        
        Args:
            event_id: Event ID
            top_k: Number of similar events to return
            use_graph: If True, use graph structure (shared venues, organizers)
        
        Returns:
            List of similar events with similarity scores
        """
        # Get target event
        cypher_event = """
        MATCH (e:Event {eventId: $eventId})
        RETURN e.eventId AS eventId,
               e.title AS title,
               e.eventType AS eventType,
               e.embedding AS embedding
        """
        
        with self.driver.session() as session:
            result = session.run(cypher_event, {"eventId": event_id})
            event = result.single()
            
            if not event:
                logger.warning(f"Event not found: {event_id}")
                return []
            
            event_data = event.data()
        
        if not event_data.get("embedding"):
            logger.warning(f"Event {event_id} has no embedding")
            return []
        
        # Vector similarity search
        event_embedding = np.array(event_data["embedding"])
        query_embedding_list = event_embedding.tolist()
        
        if use_graph:
            # Combine vector similarity + graph structure (shared venues/organizers)
            cypher = """
            CALL db.index.vector.queryNodes('event_embeddings', $topK, $queryEmbedding)
            YIELD node AS e, score AS vectorScore
            WHERE e.eventId <> $eventId
            OPTIONAL MATCH (e)-[:HELD_AT]->(v:Venue)<-[:HELD_AT]-(target:Event {eventId: $eventId})
            OPTIONAL MATCH (e)-[:ORGANIZED_BY]->(o:Organizer)<-[:ORGANIZED_BY]-(target)
            WITH e, vectorScore,
                 CASE WHEN v IS NOT NULL THEN 0.2 ELSE 0.0 END AS venueBonus,
                 CASE WHEN o IS NOT NULL THEN 0.15 ELSE 0.0 END AS organizerBonus
            WITH e, (vectorScore * 0.65 + venueBonus + organizerBonus) AS finalScore
            RETURN e.eventId AS eventId,
                   e.title AS title,
                   e.eventType AS eventType,
                   e.venue AS venue,
                   e.dateStartIso AS dateStartIso,
                   finalScore AS score
            ORDER BY finalScore DESC
            LIMIT $topK
            """
        else:
            # Pure vector similarity
            cypher = """
            CALL db.index.vector.queryNodes('event_embeddings', $topK, $queryEmbedding)
            YIELD node AS e, score
            WHERE e.eventId <> $eventId
            RETURN e.eventId AS eventId,
                   e.title AS title,
                   e.eventType AS eventType,
                   e.venue AS venue,
                   e.dateStartIso AS dateStartIso,
                   score
            ORDER BY score DESC
            """
        
        try:
            with self.driver.session() as session:
                result = session.run(cypher, {
                    "eventId": event_id,
                    "queryEmbedding": query_embedding_list,
                    "topK": top_k * 2  # Get more for filtering
                })
                return [record.data() for record in result][:top_k]
        
        except Exception as e:
            logger.error(f"Similar events search failed: {e}")
            return []
    
    # ============================================================
    # TEMPORAL ANALYTICS: Pattern recognition
    # ============================================================
    
    def analyze_temporal_patterns(
        self,
        event_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze temporal patterns in events.
        
        Returns insights like:
        - Busiest months
        - Seasonal trends
        - Day-of-week patterns
        - Recurring events
        
        Args:
            event_type: Optional filter by event type
        
        Returns:
            Dictionary with temporal analytics
        """
        filter_clause = ""
        params = {}
        
        if event_type:
            filter_clause = "WHERE toLower(e.eventType) CONTAINS toLower($eventType)"
            params["eventType"] = event_type
        
        # Month distribution
        cypher_months = f"""
        MATCH (e:Event)
        {filter_clause}
        WHERE e.dateStartIso IS NOT NULL
        WITH e, 
             toInteger(substring(e.dateStartIso, 5, 2)) AS month
        RETURN month,
               count(e) AS eventCount
        ORDER BY month
        """
        
        with self.driver.session() as session:
            result = session.run(cypher_months, params)
            monthly_data = [record.data() for record in result]
        
        # Season distribution
        seasons = {
            "winter": [12, 1, 2],
            "spring": [3, 4, 5],
            "summer": [6, 7, 8],
            "autumn": [9, 10, 11]
        }
        
        season_counts = {season: 0 for season in seasons}
        for data in monthly_data:
            month = data["month"]
            count = data["eventCount"]
            for season, months in seasons.items():
                if month in months:
                    season_counts[season] += count
        
        # Find busiest month
        busiest_month = max(monthly_data, key=lambda x: x["eventCount"]) if monthly_data else None
        
        month_names = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        
        return {
            "monthly_distribution": [
                {
                    "month": month_names[data["month"]],
                    "event_count": data["eventCount"]
                }
                for data in monthly_data
            ],
            "seasonal_distribution": season_counts,
            "busiest_month": {
                "month": month_names[busiest_month["month"]],
                "event_count": busiest_month["eventCount"]
            } if busiest_month else None,
            "busiest_season": max(season_counts.items(), key=lambda x: x[1])[0] if season_counts else None,
            "total_events_analyzed": sum(data["eventCount"] for data in monthly_data)
        }
    
    # ============================================================
    # UTILITY: Check embedding status
    # ============================================================
    
    def get_embedding_status(self) -> Dict[str, Any]:
        """
        Get statistics about embedding coverage.
        
        Returns:
            Dictionary with coverage statistics
        """
        cypher = """
        MATCH (e:Event)
        RETURN count(e) AS total,
               count(e.embedding) AS withEmbedding,
               count(e) - count(e.embedding) AS withoutEmbedding
        """
        
        with self.driver.session() as session:
            result = session.run(cypher)
            data = result.single().data()
        
        total = data["total"]
        with_embedding = data["withEmbedding"]
        
        coverage = (with_embedding / total * 100) if total > 0 else 0
        
        return {
            "total_events": total,
            "events_with_embeddings": with_embedding,
            "events_without_embeddings": data["withoutEmbedding"],
            "coverage_percentage": round(coverage, 2),
            "model_name": self.model_name,
            "embedding_dimensions": 768
        }
