"""Repository for event database operations.

Manages Event, EventType, Venue, and Organizer nodes in Neo4j, including:
- Schema initialization (constraints + indexes)
- Bulk loading from events.json
- Relationship creation (HAS_TYPE, HELD_AT, ORGANIZED_BY, BELONGS_TO_DOMAIN)
- Querying with dynamic filters
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from neo4j import Driver

from .base import BaseRepository
from ..utils import DatabasePaths
from core.gcs_downloader import refresh_events

logger = logging.getLogger(__name__)


class EventRepository(BaseRepository):
    """Repository for managing event data in Neo4j."""

    def __init__(self, driver: Driver):
        super().__init__(driver)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def load_schema(self) -> Dict[str, Any]:
        """Load event schema (constraints and indexes)."""
        return self.load_schema_from_file("init_events_schema.cypher")

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def load_from_file(self, file_path: str = None) -> Dict[str, Any]:
        """Load events from events.json.

        Args:
            file_path: Optional path to events.json.
                       Defaults to data/events.json.

        Returns:
            Dictionary with success status and statistics.
        """
        try:
            if file_path is None:
                file_path = str(DatabasePaths.get_data_directory() / "events.json")

            # Try to refresh from GCS first; fall back to the local file on failure
            refresh_events(file_path)

            data_path = Path(file_path)
            if not data_path.exists():
                raise FileNotFoundError(f"Events file not found: {data_path}")

            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            events = data.get("events", [])
            if not events:
                return {
                    "success": True,
                    "message": "No events found in file",
                    "events_created": 0,
                }

            logger.info(f"Found {len(events)} events to process")

            total_events = 0
            total_types = 0
            total_venues = 0
            total_organizers = 0
            total_relationships = 0
            errors: List[str] = []

            # Pre-create EventType nodes
            event_types = set(e.get("event_type", "").strip() for e in events if e.get("event_type"))
            total_types = self._ensure_event_types(event_types)

            # Pre-create Venue nodes
            venues = set(e.get("venue", "").strip() for e in events if e.get("venue"))
            total_venues = self._ensure_venues(venues)

            # Pre-create Organizer nodes
            organizers = set(e.get("organizer", "").strip() for e in events if e.get("organizer"))
            total_organizers = self._ensure_organizers(organizers)

            # Ensure the "Event & Activity" domain node exists
            self._ensure_domain()

            # Create events and relationships
            for event in events:
                try:
                    result = self._create_event(event)
                    total_events += result.get("created", 0)
                    total_relationships += result.get("relationships", 0)
                except Exception as e:
                    eid = event.get("event_id", "?")
                    error_msg = f"Failed to process event {eid}: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            logger.info(
                f"Event loading complete: {total_events} events, "
                f"{total_types} types, {total_venues} venues, "
                f"{total_organizers} organizers, {total_relationships} relationships"
            )

            return {
                "events_created": total_events,
                "event_types_created": total_types,
                "venues_created": total_venues,
                "organizers_created": total_organizers,
                "relationships_created": total_relationships,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Failed to load events: {e}")
            raise

    # ------------------------------------------------------------------
    # Pre-creation helpers
    # ------------------------------------------------------------------

    def _ensure_event_types(self, types: set) -> int:
        """Create EventType nodes."""
        count = 0
        for t in types:
            if not t:
                continue
            cypher = """
            MERGE (et:EventType {name: $name})
            ON CREATE SET et.createdAt = datetime()
            RETURN et.name AS name
            """
            with self.driver.session() as session:
                session.run(cypher, {"name": t})
                count += 1
        logger.info(f"Ensured {count} EventType nodes")
        return count

    def _ensure_venues(self, venues: set) -> int:
        """Create Venue nodes."""
        count = 0
        for v in venues:
            if not v:
                continue
            cypher = """
            MERGE (ve:Venue {name: $name})
            ON CREATE SET ve.createdAt = datetime()
            RETURN ve.name AS name
            """
            with self.driver.session() as session:
                session.run(cypher, {"name": v})
                count += 1
        logger.info(f"Ensured {count} Venue nodes")
        return count

    def _ensure_organizers(self, organizers: set) -> int:
        """Create Organizer nodes."""
        count = 0
        for o in organizers:
            if not o:
                continue
            cypher = """
            MERGE (org:Organizer {name: $name})
            ON CREATE SET org.createdAt = datetime()
            RETURN org.name AS name
            """
            with self.driver.session() as session:
                session.run(cypher, {"name": o})
                count += 1
        logger.info(f"Ensured {count} Organizer nodes")
        return count

    def _ensure_domain(self):
        """Ensure the 'Event & Activity' Domain node exists."""
        cypher = """
        MERGE (d:Domain {name: 'Event & Activity'})
        ON CREATE SET d.description = 'Public events, festivals, shows, conferences, and activities in Sri Lanka',
                      d.createdAt = datetime()
        RETURN d.name AS name
        """
        with self.driver.session() as session:
            session.run(cypher)
        logger.info("Ensured 'Event & Activity' domain node")

    # ------------------------------------------------------------------
    # Event creation
    # ------------------------------------------------------------------

    def _create_event(self, event: Dict[str, Any]) -> Dict[str, int]:
        """Create a single Event node and wire up relationships.

        Returns:
            Dict with 'created' and 'relationships' counts.
        """
        event_id = str(event.get("event_id", "")).strip()
        if not event_id:
            return {"created": 0, "relationships": 0}

        # Collect image URLs
        images = event.get("images", [])
        image_url = images[0].get("direct_url") if images else None

        # Build properties
        props = {
            "eventId": event_id,
            "title": event.get("title", "").strip(),
            "eventType": event.get("event_type", "").strip(),
            "organizer": event.get("organizer", "").strip(),
            "venue": event.get("venue", "").strip(),
            "hasGoogleMaps": event.get("has_google_maps", False),
            "dateStart": event.get("date_start"),
            "dateEnd": event.get("date_end"),
            "dateStartIso": event.get("date_start_iso"),
            "dateEndIso": event.get("date_end_iso"),
            "timeStart": event.get("time_start"),
            "timeEnd": event.get("time_end"),
            "description": (event.get("description") or "")[:2000],
            "visibility": event.get("visibility", "PUBLIC"),
            "imageUrl": image_url,
            "hashtags": event.get("hashtags"),
            "eventDetailUrl": event.get("event_detail_url"),
            "icalLink": event.get("ical_link"),
            "googleCalendarLink": event.get("google_calendar_link"),
        }

        # MERGE the Event node
        cypher = """
        MERGE (e:Event {eventId: $eventId})
        ON CREATE SET e += $props, e.createdAt = datetime()
        ON MATCH  SET e += $props, e.updatedAt = datetime()
        RETURN e.eventId AS eid
        """
        with self.driver.session() as session:
            session.run(cypher, {"eventId": event_id, "props": props})

        rels = 0

        # Relationship: HAS_TYPE → EventType
        event_type = event.get("event_type", "").strip()
        if event_type:
            rels += self._link(event_id, "HAS_TYPE", "EventType", "name", event_type)

        # Relationship: HELD_AT → Venue
        venue = event.get("venue", "").strip()
        if venue:
            rels += self._link(event_id, "HELD_AT", "Venue", "name", venue)

        # Relationship: ORGANIZED_BY → Organizer
        organizer = event.get("organizer", "").strip()
        if organizer:
            rels += self._link(event_id, "ORGANIZED_BY", "Organizer", "name", organizer)

        # Relationship: BELONGS_TO_DOMAIN → Domain
        rels += self._link(event_id, "BELONGS_TO_DOMAIN", "Domain", "name", "Event & Activity")

        # Temporal relationships: IN_MONTH, IN_YEAR
        rels += self._link_temporal(event_id, event.get("date_start_iso"))

        return {"created": 1, "relationships": rels}

    def _link(
        self,
        event_id: str,
        rel_type: str,
        target_label: str,
        target_key: str,
        target_value: str,
    ) -> int:
        """Create a relationship from an Event to a target node."""
        cypher = f"""
        MATCH (e:Event {{eventId: $eventId}})
        MATCH (t:{target_label} {{{target_key}: $targetValue}})
        MERGE (e)-[:{rel_type}]->(t)
        RETURN count(*) AS c
        """
        try:
            with self.driver.session() as session:
                session.run(cypher, {"eventId": event_id, "targetValue": target_value})
            return 1
        except Exception as exc:
            logger.debug(f"Failed to link Event({event_id}) -[{rel_type}]-> {target_label}({target_value}): {exc}")
            return 0

    def _link_temporal(self, event_id: str, date_iso: Optional[str]) -> int:
        """Link event to Year and Month nodes (reuse existing temporal pattern)."""
        if not date_iso:
            return 0

        rels = 0
        try:
            parts = date_iso.split("-")
            year_str = parts[0]
            month_num = int(parts[1])
            from core.constants import MONTHS
            month_name = MONTHS[month_num - 1]

            # Link to Year
            cypher_year = """
            MATCH (e:Event {eventId: $eventId})
            MERGE (y:Year {year: $year})
            MERGE (e)-[:IN_YEAR]->(y)
            """
            with self.driver.session() as session:
                session.run(cypher_year, {"eventId": event_id, "year": int(year_str)})
            rels += 1

            # Link to Month
            cypher_month = """
            MATCH (e:Event {eventId: $eventId})
            MERGE (m:Month {name: $month})
            MERGE (e)-[:IN_MONTH]->(m)
            """
            with self.driver.session() as session:
                session.run(cypher_month, {"eventId": event_id, "month": month_name})
            rels += 1

        except Exception as exc:
            logger.debug(f"Failed temporal link for Event({event_id}): {exc}")

        return rels

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> Dict[str, Any]:
        """Remove all Event, EventType, Venue, Organizer nodes and relationships."""
        labels = ["Event", "EventType", "Venue", "Organizer"]
        deleted = {}
        for label in labels:
            cypher = f"MATCH (n:{label}) DETACH DELETE n RETURN count(n) AS c"
            with self.driver.session() as session:
                result = session.run(cypher)
                record = result.single()
                deleted[label] = record["c"] if record else 0
        logger.info(f"Cleanup complete: {deleted}")
        return deleted

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def query(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query events with dynamic filters.

        Supported filter keys: event_type, venue, organizer, month,
        date_from, date_to, query, limit.
        """
        where_clauses: List[str] = []
        cypher_params: Dict[str, Any] = {}

        if params.get("event_type"):
            where_clauses.append("toLower(e.eventType) CONTAINS toLower($eventType)")
            cypher_params["eventType"] = params["event_type"]

        if params.get("venue"):
            where_clauses.append("toLower(e.venue) CONTAINS toLower($venue)")
            cypher_params["venue"] = params["venue"]

        if params.get("organizer"):
            where_clauses.append("toLower(e.organizer) CONTAINS toLower($organizer)")
            cypher_params["organizer"] = params["organizer"]

        if params.get("date_from"):
            where_clauses.append("e.dateStartIso >= $dateFrom")
            cypher_params["dateFrom"] = params["date_from"]

        if params.get("date_to"):
            where_clauses.append("e.dateEndIso <= $dateTo")
            cypher_params["dateTo"] = params["date_to"]

        if params.get("query"):
            where_clauses.append(
                "(toLower(e.title) CONTAINS toLower($q) "
                "OR toLower(e.description) CONTAINS toLower($q))"
            )
            cypher_params["q"] = params["query"]

        limit = min(params.get("limit", 20), 100)
        cypher_params["limit"] = limit

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
               e.visibility AS visibility,
               e.hashtags AS hashtags,
               e.imageUrl AS imageUrl,
               e.eventDetailUrl AS eventDetailUrl
        ORDER BY e.dateStartIso ASC
        LIMIT $limit
        """

        return self.execute_query(cypher, cypher_params)

    def get_by_type(self, event_type: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get events by type."""
        return self.query({"event_type": event_type, "limit": limit})

    def get_by_venue(self, venue: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get events by venue."""
        return self.query({"venue": venue, "limit": limit})

    def get_by_organizer(self, organizer: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get events by organizer."""
        return self.query({"organizer": organizer, "limit": limit})

    def get_upcoming(self, from_date: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get upcoming events from a given date (ISO format)."""
        if from_date is None:
            from datetime import date
            from_date = date.today().isoformat()
        return self.query({"date_from": from_date, "limit": limit})

    def get_event_types(self) -> List[Dict[str, Any]]:
        """Get all distinct event types with counts."""
        cypher = """
        MATCH (et:EventType)<-[:HAS_TYPE]-(e:Event)
        RETURN et.name AS eventType, count(e) AS eventCount
        ORDER BY eventCount DESC
        """
        return self.execute_query(cypher)

    def get_venues(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get venues with event counts."""
        cypher = """
        MATCH (v:Venue)<-[:HELD_AT]-(e:Event)
        RETURN v.name AS venue, count(e) AS eventCount
        ORDER BY eventCount DESC
        LIMIT $limit
        """
        return self.execute_query(cypher, {"limit": limit})

    def get_organizers(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get organizers with event counts."""
        cypher = """
        MATCH (org:Organizer)<-[:ORGANIZED_BY]-(e:Event)
        RETURN org.name AS organizer, count(e) AS eventCount
        ORDER BY eventCount DESC
        LIMIT $limit
        """
        return self.execute_query(cypher, {"limit": limit})

    def get_statistics(self) -> Dict[str, Any]:
        """Get event knowledge-graph statistics."""
        cypher = """
        MATCH (e:Event)
        WITH count(e) AS totalEvents
        OPTIONAL MATCH (et:EventType)
        WITH totalEvents, count(et) AS totalTypes
        OPTIONAL MATCH (v:Venue)
        WITH totalEvents, totalTypes, count(v) AS totalVenues
        OPTIONAL MATCH (org:Organizer)
        RETURN totalEvents, totalTypes, totalVenues, count(org) AS totalOrganizers
        """
        result = self.execute_query(cypher)
        row = result[0] if result else {}

        # Events by type
        type_cypher = """
        MATCH (e:Event)-[:HAS_TYPE]->(et:EventType)
        RETURN et.name AS eventType, count(e) AS cnt
        ORDER BY cnt DESC
        """
        type_counts = self.execute_query(type_cypher)
        by_type = {r["eventType"]: r["cnt"] for r in type_counts}

        # Events by month
        month_cypher = """
        MATCH (e:Event)-[:IN_MONTH]->(m:Month)
        RETURN m.name AS month, count(e) AS cnt
        ORDER BY cnt DESC
        """
        month_counts = self.execute_query(month_cypher)
        by_month = {r["month"]: r["cnt"] for r in month_counts}

        return {
            "total_events": row.get("totalEvents", 0),
            "total_event_types": row.get("totalTypes", 0),
            "total_venues": row.get("totalVenues", 0),
            "total_organizers": row.get("totalOrganizers", 0),
            "events_by_type": by_type,
            "events_by_month": by_month,
        }
