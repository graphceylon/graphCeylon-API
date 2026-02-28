"""
Orchestrator Event Service

Business logic for event search functionality.
Provides intelligent search across events in the knowledge graph.

The request/response contract mirrors the attraction orchestrator so the
centralized orchestrator can call this endpoint with the same payload shape.
"""

import logging
from typing import List, Dict, Any, Optional

from neo4j import Driver

from models.domain.event import (
    EventSearchRequest,
    EventItem,
    EventSearchResponse,
)

logger = logging.getLogger(__name__)


class OrchestratorEventService:
    """Service for handling orchestrator event search requests.

    Mirrors the contract of ``OrchestratorAttractionService`` so the
    orchestrator can call ``/orchestrator/call/events`` with the same
    payload shape used for ``/orchestrator/call/attractions``.
    """

    def __init__(self, driver: Driver):
        self.driver = driver

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_events(
        self, request: EventSearchRequest
    ) -> EventSearchResponse:
        """Search events using various strategy patterns.

        1. City only (no poi_category): Events at venues matching city name
        2. City + poi_category: Filtered by venue city + event type
        3. poi_category only: Events of that type across all venues
        4. poi_name: Search by event name
        5. tags: Match against event hashtags
        """
        try:
            city = request.city or ""

            results = self._get_events(
                city=city,
                event_name=request.poi_name,
                event_type=request.poi_category,
                tags=request.tags,
                limit=20,
            )

            items = [self._map_to_item(r) for r in results]

            summary = self._generate_summary(
                items=items,
                city=city,
                days=request.days,
            )

            return EventSearchResponse(
                ok=True,
                city=city or "all",
                country=request.country,
                items=items,
                summary=summary,
            )

        except Exception as e:
            logger.error(f"Event search failed: {e}")
            return EventSearchResponse(
                ok=False,
                city=request.city or "",
                country=request.country,
                items=[],
                summary="",
                error="search_failed",
                details=str(e),
            )

    # ------------------------------------------------------------------
    # Neo4j query
    # ------------------------------------------------------------------

    def _get_events(
        self,
        city: str = "",
        event_name: Optional[str] = None,
        event_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch events from Neo4j with filters."""

        where_clauses: List[str] = []
        params: Dict[str, Any] = {"limit": limit}

        # City / venue filter
        if city:
            where_clauses.append(
                "(toLower(e.venue) CONTAINS toLower($city) "
                "OR toLower(e.title) CONTAINS toLower($city) "
                "OR toLower(e.hashtags) CONTAINS toLower($city))"
            )
            params["city"] = city

        # Event name search
        if event_name:
            where_clauses.append("toLower(e.title) CONTAINS toLower($eventName)")
            params["eventName"] = event_name

        # Event type filter
        if event_type and event_type.strip():
            where_clauses.append("toLower(e.eventType) CONTAINS toLower($eventType)")
            params["eventType"] = event_type.strip()

        # Tag filter (match against hashtags)
        if tags:
            tag_clauses = []
            for i, tag in enumerate(tags):
                tag_param = f"tag{i}"
                tag_clauses.append(
                    f"(toLower(e.hashtags) CONTAINS toLower(${tag_param}) "
                    f"OR toLower(e.title) CONTAINS toLower(${tag_param}) "
                    f"OR toLower(e.eventType) CONTAINS toLower(${tag_param}))"
                )
                params[tag_param] = tag
            if tag_clauses:
                where_clauses.append(f"({' OR '.join(tag_clauses)})")

        # Only PUBLIC events
        where_clauses.append("e.visibility = 'PUBLIC'")

        where_clause = " AND ".join(where_clauses) if where_clauses else "true"

        cypher = f"""
        MATCH (e:Event)
        WHERE {where_clause}
        OPTIONAL MATCH (e)-[:HAS_TYPE]->(et:EventType)
        OPTIONAL MATCH (e)-[:HELD_AT]->(v:Venue)
        OPTIONAL MATCH (e)-[:ORGANIZED_BY]->(org:Organizer)
        RETURN e.eventId AS eventId,
               e.title AS title,
               e.eventType AS eventType,
               e.organizer AS organizer,
               e.venue AS venue,
               e.dateStart AS dateStart,
               e.dateEnd AS dateEnd,
               e.dateStartIso AS dateStartIso,
               e.dateEndIso AS dateEndIso,
               e.timeStart AS timeStart,
               e.timeEnd AS timeEnd,
               e.description AS description,
               e.hashtags AS hashtags,
               e.imageUrl AS imageUrl,
               e.eventDetailUrl AS eventDetailUrl
        ORDER BY e.dateStartIso ASC
        LIMIT $limit
        """

        with self.driver.session() as session:
            result = session.run(cypher, params)
            return [record.data() for record in result]

    # ------------------------------------------------------------------
    # Mapping (mirrors attraction service _map_to_item pattern)
    # ------------------------------------------------------------------

    def _map_to_item(self, data: Dict[str, Any]) -> EventItem:
        """Map a Neo4j event record to ``EventItem``."""

        open_hours = self._build_schedule_string(data)

        # Truncate description for the summary view
        description = data.get("description") or None
        if description and len(description) > 300:
            description = description[:297] + "..."

        return EventItem(
            name=data.get("title", "Unknown Event"),
            category=data.get("eventType"),
            description=description,
            location=data.get("venue"),
            open_hours=open_hours,
            entry_fee_lkr="Contact organizer",
            source="kg_service",
            rating=None,
            coordinates=None,
            website=data.get("eventDetailUrl"),
            phone=None,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_schedule_string(data: Dict[str, Any]) -> Optional[str]:
        """Build a human-readable schedule string from date and time fields."""
        date_start = data.get("dateStart") or data.get("dateStartIso")
        date_end = data.get("dateEnd") or data.get("dateEndIso")
        time_start = data.get("timeStart")
        time_end = data.get("timeEnd")

        parts = []

        # Date part
        if date_start and date_end and date_start != date_end:
            parts.append(f"{date_start} – {date_end}")
        elif date_start:
            parts.append(date_start)

        # Time part
        if time_start and time_end:
            parts.append(f"{time_start} – {time_end}")
        elif time_start:
            parts.append(f"from {time_start}")

        return " | ".join(parts) if parts else None

    @staticmethod
    def _generate_summary(
        items: List[EventItem],
        city: str,
        days: Optional[int] = None,
    ) -> str:
        """Generate a natural-language summary matching the attraction service style."""
        if not items:
            location = f"in {city}" if city else "matching your criteria"
            return f"No events found {location}."

        count = len(items)
        categories: Dict[str, int] = {}
        for item in items:
            cat = item.category or "event"
            categories[cat] = categories.get(cat, 0) + 1

        top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
        cat_text = ", ".join(
            f"{c} {name}{'s' if c > 1 else ''}" for name, c in top_cats
        )

        location_text = f"in {city}" if city and city not in ("all", "") else "in Sri Lanka"
        summary = f"Found {count} event{'s' if count != 1 else ''} {location_text}"
        if cat_text:
            summary += f" including {cat_text}"

        if days:
            if days == 1:
                summary += ". Great options for a single day"
            elif days <= 3:
                summary += f". Plenty of activities for a {days}-day trip"
            else:
                summary += f". A rich calendar for {days} days of exploration"

        return summary + "."
