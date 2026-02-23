"""
Bus Schedule Repository

Database operations for bus terminals, schedules, and depots.
Handles Cypher queries for the Transportation Domain.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from neo4j import Driver

from .base import BaseRepository

logger = logging.getLogger(__name__)


class BusScheduleRepository(BaseRepository):
    """Repository for bus terminal and schedule operations."""

    def __init__(self, driver: Driver):
        super().__init__(driver)
        self.domain_name = "Transportation"

    # ==========================================================
    # Schema
    # ==========================================================

    def load_schema(self) -> Dict[str, Any]:
        """Load bus schedule schema (constraints & indexes)."""
        try:
            return self.load_schema_from_file("init_bus_schedule_schema.cypher")
        except Exception as e:
            logger.error(f"Failed to load bus schedule schema: {e}")
            return {"success": False, "error": str(e)}

    # ==========================================================
    # Bus Terminal CRUD
    # ==========================================================

    def create_bus_terminal(self, terminal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a single BusTerminal node in the knowledge graph."""
        cypher = """
        MATCH (domain:Domain {name: $domain_name})

        MERGE (bt:BusTerminal:TransportationInfrastructure {name: $name})
        ON CREATE SET
            bt.enriched            = $enriched,
            bt.geocoded            = $geocoded,
            bt.latitude            = $latitude,
            bt.longitude           = $longitude,
            bt.place_id            = $place_id,
            bt.formatted_address   = $formatted_address,
            bt.location_type       = $location_type,
            bt.province            = $province,
            bt.district            = $district,
            bt.city                = $city,
            bt.town                = $town,
            bt.google_rating       = $google_rating,
            bt.user_ratings_total  = $user_ratings_total,
            bt.website             = $website,
            bt.phone               = $phone,
            bt.business_status     = $business_status,
            bt.google_maps_url     = $google_maps_url,
            bt.place_types         = $place_types,
            bt.vicinity            = $vicinity,
            bt.google_data_json    = $google_data_json,
            bt.created_at          = datetime()

        MERGE (bt)-[:BELONGS_TO_DOMAIN]->(domain)

        WITH bt
        OPTIONAL MATCH (prov:Province {name: bt.province})
        FOREACH (_ IN CASE WHEN prov IS NOT NULL THEN [1] ELSE [] END |
            MERGE (bt)-[:LOCATED_IN_PROVINCE]->(prov)
        )

        WITH bt
        OPTIONAL MATCH (dist:District {name: bt.district})
        FOREACH (_ IN CASE WHEN dist IS NOT NULL THEN [1] ELSE [] END |
            MERGE (bt)-[:LOCATED_IN_DISTRICT]->(dist)
        )

        RETURN bt
        """

        google = terminal_data.get("google_data") or {}
        coords = google.get("coordinates") or {}
        admin = google.get("administrative_areas") or {}

        params = {
            "domain_name": self.domain_name,
            "name": terminal_data.get("location_name"),
            "enriched": terminal_data.get("enriched", False),
            "geocoded": terminal_data.get("geocoded", False),
            "latitude": coords.get("lat"),
            "longitude": coords.get("lon"),
            "place_id": google.get("place_id"),
            "formatted_address": google.get("formatted_address"),
            "location_type": google.get("location_type"),
            "province": admin.get("province"),
            "district": admin.get("district"),
            "city": admin.get("city"),
            "town": admin.get("town"),
            "google_rating": google.get("rating"),
            "user_ratings_total": google.get("user_ratings_total"),
            "website": google.get("website"),
            "phone": google.get("phone"),
            "business_status": google.get("business_status"),
            "google_maps_url": google.get("google_maps_url"),
            "place_types": google.get("place_types"),
            "vicinity": google.get("vicinity"),
            "google_data_json": json.dumps(google) if google else None,
        }

        result = self.execute_query(cypher, params)
        return result[0] if result else {}

    def get_bus_terminals(
        self,
        province: Optional[str] = None,
        district: Optional[str] = None,
        name_pattern: Optional[str] = None,
        has_rating: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Query bus terminals with optional filters."""
        cypher = """
        MATCH (bt:BusTerminal)
        WHERE 1=1
        {province_filter}
        {district_filter}
        {name_filter}
        {rating_filter}
        RETURN properties(bt) as terminal
        ORDER BY bt.name
        LIMIT $limit
        """

        filters = {
            "province_filter": "AND bt.province = $province" if province else "",
            "district_filter": "AND bt.district = $district" if district else "",
            "name_filter": "AND toLower(bt.name) CONTAINS toLower($name_pattern)" if name_pattern else "",
            "rating_filter": "AND bt.google_rating IS NOT NULL" if has_rating else "",
        }
        cypher = cypher.format(**filters)

        params = {
            "limit": limit,
            "province": province,
            "district": district,
            "name_pattern": name_pattern,
        }

        return self.execute_query(cypher, params)

    def get_terminal_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific bus terminal by exact name."""
        cypher = """
        MATCH (bt:BusTerminal)
        WHERE toLower(bt.name) = toLower($name)
        RETURN properties(bt) as terminal
        LIMIT 1
        """
        result = self.execute_query(cypher, {"name": name})
        return result[0] if result else None

    def search_terminals(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Full-text search on bus terminal name / address."""
        cypher = """
        CALL db.index.fulltext.queryNodes('bus_terminal_search', $query)
        YIELD node, score
        RETURN properties(node) as terminal, score
        ORDER BY score DESC
        LIMIT $limit
        """
        return self.execute_query(cypher, {"query": query, "limit": limit})

    # ==========================================================
    # Bus Schedule CRUD
    # ==========================================================

    def create_bus_schedule(self, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a BusSchedule node and link to origin/destination terminals and depot."""
        cypher = """
        MATCH (domain:Domain {name: $domain_name})

        // Create the schedule node
        MERGE (bs:BusSchedule:TransportationService {schedule_id: $schedule_id})
        ON CREATE SET
            bs.schedule_date       = $schedule_date,
            bs.departure_date      = $departure_date,
            bs.departure_time      = $departure_time,
            bs.arrival_date        = $arrival_date,
            bs.arrival_time        = $arrival_time,
            bs.origin              = $origin,
            bs.destination         = $destination,
            bs.bus_type            = $bus_type,
            bs.fare                = $fare,
            bs.model               = $model,
            bs.route_no            = $route_no,
            bs.seats_available     = $seats_available,
            bs.booking_link        = $booking_link,
            bs.booking_closing_date = $booking_closing_date,
            bs.booking_closing_time = $booking_closing_time,
            bs.boarding_points_json = $boarding_points_json,
            bs.dropping_points_json = $dropping_points_json,
            bs.created_at          = datetime()

        MERGE (bs)-[:BELONGS_TO_DOMAIN]->(domain)

        // Link to depot
        WITH bs, domain
        MERGE (depot:BusDepot {name: $depot_name})
        ON CREATE SET depot.created_at = datetime()
        MERGE (depot)-[:BELONGS_TO_DOMAIN]->(domain)
        MERGE (bs)-[:OPERATED_BY_DEPOT]->(depot)

        // Link to origin terminal (MERGE – create if not pre-loaded)
        WITH bs
        MERGE (origin_bt:BusTerminal {name: $origin})
        MERGE (bs)-[:DEPARTS_FROM]->(origin_bt)

        // Link to destination terminal
        WITH bs, origin_bt
        MERGE (dest_bt:BusTerminal {name: $destination})
        MERGE (bs)-[:ARRIVES_AT]->(dest_bt)

        // Create direct connectivity edge
        MERGE (origin_bt)-[conn:CONNECTED_BY_BUS]->(dest_bt)
        ON CREATE SET conn.created_at = datetime(), conn.route_count = 1
        ON MATCH  SET conn.route_count = conn.route_count + 1,
                      conn.updated_at = datetime()

        RETURN bs
        """

        # Parse fare safely
        fare = schedule_data.get("fare")
        if fare is not None:
            try:
                fare = float(fare)
            except (ValueError, TypeError):
                fare = None

        # Parse seats
        seats = schedule_data.get("seats_available")
        if seats is not None:
            try:
                seats = int(seats)
            except (ValueError, TypeError):
                seats = None

        params = {
            "domain_name": self.domain_name,
            "schedule_id": schedule_data.get("bus_schedule_id"),
            "schedule_date": schedule_data.get("date"),
            "departure_date": schedule_data.get("departure_date"),
            "departure_time": schedule_data.get("departure_time"),
            "arrival_date": schedule_data.get("arrival_date"),
            "arrival_time": schedule_data.get("arrival_time"),
            "origin": schedule_data.get("from"),
            "destination": schedule_data.get("to"),
            "depot_name": schedule_data.get("depot_name"),
            "bus_type": schedule_data.get("bus_type", "Normal"),
            "fare": fare,
            "model": schedule_data.get("model"),
            "route_no": schedule_data.get("route_no") or None,
            "seats_available": seats,
            "booking_link": schedule_data.get("booking_link"),
            "booking_closing_date": schedule_data.get("booking_closing_date"),
            "booking_closing_time": schedule_data.get("booking_closing_time"),
            "boarding_points_json": schedule_data.get("boarding_points"),
            "dropping_points_json": schedule_data.get("dropping_points"),
        }

        result = self.execute_query(cypher, params)
        return result[0] if result else {}

    def get_bus_schedules(
        self,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        schedule_date: Optional[str] = None,
        depot_name: Optional[str] = None,
        max_fare: Optional[float] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Query bus schedules with optional filters."""
        cypher = """
        MATCH (bs:BusSchedule)
        WHERE 1=1
        {origin_filter}
        {dest_filter}
        {date_filter}
        {depot_filter}
        {fare_filter}
        OPTIONAL MATCH (bs)-[:OPERATED_BY_DEPOT]->(depot:BusDepot)
        RETURN properties(bs) as schedule, depot.name as depot_name
        ORDER BY bs.departure_time
        LIMIT $limit
        """

        filters = {
            "origin_filter": "AND toLower(bs.origin) = toLower($origin)" if origin else "",
            "dest_filter": "AND toLower(bs.destination) = toLower($destination)" if destination else "",
            "date_filter": "AND bs.schedule_date = $schedule_date" if schedule_date else "",
            "depot_filter": "AND EXISTS { MATCH (bs)-[:OPERATED_BY_DEPOT]->(d:BusDepot {name: $depot_name}) }" if depot_name else "",
            "fare_filter": "AND bs.fare <= $max_fare" if max_fare is not None else "",
        }
        cypher = cypher.format(**filters)

        params = {
            "limit": limit,
            "origin": origin,
            "destination": destination,
            "schedule_date": schedule_date,
            "depot_name": depot_name,
            "max_fare": max_fare,
        }

        results = self.execute_query(cypher, params)

        # Attach depot_name into schedule dict
        for r in results:
            if "schedule" in r:
                r["schedule"]["depot_name"] = r.get("depot_name")
        return [r.get("schedule", {}) for r in results]

    def find_bus_routes(
        self,
        origin: str,
        destination: str,
        schedule_date: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find bus routes between two cities."""
        cypher = """
        MATCH (bs:BusSchedule)
        WHERE toLower(bs.origin) = toLower($origin)
          AND toLower(bs.destination) = toLower($destination)
        {date_filter}
        OPTIONAL MATCH (bs)-[:OPERATED_BY_DEPOT]->(depot:BusDepot)
        RETURN properties(bs) as schedule, depot.name as depot_name
        ORDER BY bs.fare, bs.departure_time
        LIMIT $limit
        """

        date_filter = "AND bs.schedule_date = $schedule_date" if schedule_date else ""
        cypher = cypher.format(date_filter=date_filter)

        params = {
            "origin": origin,
            "destination": destination,
            "schedule_date": schedule_date,
            "limit": limit,
        }

        results = self.execute_query(cypher, params)
        for r in results:
            if "schedule" in r:
                r["schedule"]["depot_name"] = r.get("depot_name")
        return [r.get("schedule", {}) for r in results]

    # ==========================================================
    # Statistics
    # ==========================================================

    def get_terminal_statistics(self) -> Dict[str, Any]:
        """Get statistics about bus terminals."""
        cypher = """
        MATCH (bt:BusTerminal)
        WITH count(bt) as total,
             sum(CASE WHEN bt.enriched = true THEN 1 ELSE 0 END) as enriched,
             sum(CASE WHEN bt.google_rating IS NOT NULL THEN 1 ELSE 0 END) as with_rating,
             sum(CASE WHEN bt.business_status = 'OPERATIONAL' THEN 1 ELSE 0 END) as operational

        CALL {
            MATCH (b:BusTerminal) WHERE b.province IS NOT NULL
            WITH b.province as province, count(b) as cnt
            ORDER BY cnt DESC
            RETURN collect({province: province, count: cnt}) as prov_stats
        }
        CALL {
            MATCH (b:BusTerminal) WHERE b.district IS NOT NULL
            WITH b.district as district, count(b) as cnt
            ORDER BY cnt DESC
            RETURN collect({district: district, count: cnt}) as dist_stats
        }

        RETURN {
            total_terminals: total,
            enriched_terminals: enriched,
            with_rating: with_rating,
            operational: operational,
            terminals_by_province: prov_stats,
            terminals_by_district: dist_stats
        } as statistics
        """
        result = self.execute_query(cypher, {})
        return result[0].get("statistics", {}) if result else {}

    def get_schedule_statistics(self) -> Dict[str, Any]:
        """Get statistics about bus schedules."""
        cypher = """
        MATCH (bs:BusSchedule)
        WITH count(bs) as total,
             count(DISTINCT bs.origin) as origins,
             count(DISTINCT bs.destination) as dests,
             min(bs.fare) as min_fare,
             max(bs.fare) as max_fare

        CALL {
            MATCH (bs2:BusSchedule)-[:OPERATED_BY_DEPOT]->(d:BusDepot)
            WITH d.name as depot, count(bs2) as cnt
            ORDER BY cnt DESC
            RETURN count(DISTINCT d.name) as depot_count,
                   collect({depot: depot, count: cnt}) as depot_stats
        }
        CALL {
            MATCH (bs3:BusSchedule)
            WITH bs3.origin as origin, count(bs3) as cnt
            ORDER BY cnt DESC
            RETURN collect({origin: origin, count: cnt}) as origin_stats
        }

        RETURN {
            total_schedules: total,
            unique_origins: origins,
            unique_destinations: dests,
            unique_depots: depot_count,
            fare_range: {min: min_fare, max: max_fare},
            schedules_by_depot: depot_stats,
            schedules_by_origin: origin_stats
        } as statistics
        """
        result = self.execute_query(cypher, {})
        return result[0].get("statistics", {}) if result else {}

    # ==========================================================
    # Bulk Loading
    # ==========================================================

    def load_terminals_from_json(self, json_file_path: str) -> Dict[str, Any]:
        """Bulk load bus terminals from the enriched JSON file."""
        try:
            file_path = Path(json_file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"JSON file not found: {json_file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            locations = data.get("locations", [])
            total = len(locations)
            created = 0
            errors: List[Dict[str, Any]] = []

            logger.info(f"Loading {total} bus terminals from {json_file_path}")

            for idx, loc in enumerate(locations):
                try:
                    self.create_bus_terminal(loc)
                    created += 1
                    if (idx + 1) % 200 == 0:
                        logger.info(f"  Loaded {idx + 1}/{total} terminals...")
                except Exception as e:
                    logger.error(f"Error loading terminal {loc.get('location_name', '?')}: {e}")
                    errors.append({"terminal": loc.get("location_name"), "error": str(e)})

            logger.info(f"Completed loading {created}/{total} bus terminals")
            return {
                "success": True,
                "total": total,
                "created": created,
                "failed": len(errors),
                "errors": errors[:10],
            }

        except Exception as e:
            logger.error(f"Failed to load terminals from JSON: {e}")
            return {"success": False, "error": str(e)}

    def load_schedules_from_csv(self, csv_file_path: str) -> Dict[str, Any]:
        """Bulk load bus schedules from CSV file."""
        try:
            file_path = Path(csv_file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"CSV file not found: {csv_file_path}")

            created = 0
            skipped = 0
            depots_seen: set = set()
            errors: List[Dict[str, Any]] = []

            logger.info(f"Loading bus schedules from {csv_file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                total = len(rows)

                for idx, row in enumerate(rows):
                    try:
                        schedule_id = row.get("bus_schedule_id")
                        if not schedule_id:
                            skipped += 1
                            continue

                        # Track depot names
                        depot = row.get("depot_name")
                        if depot:
                            depots_seen.add(depot)

                        self.create_bus_schedule(row)
                        created += 1

                        if (idx + 1) % 50 == 0:
                            logger.info(f"  Loaded {idx + 1}/{total} schedules...")
                    except Exception as e:
                        logger.error(f"Error loading schedule {row.get('bus_schedule_id', '?')}: {e}")
                        errors.append({"schedule_id": row.get("bus_schedule_id"), "error": str(e)})

            logger.info(f"Completed loading {created}/{total} bus schedules ({len(depots_seen)} depots)")
            return {
                "success": True,
                "total": total,
                "created": created,
                "skipped": skipped,
                "failed": len(errors),
                "depots_created": len(depots_seen),
                "errors": errors[:10],
            }

        except Exception as e:
            logger.error(f"Failed to load schedules from CSV: {e}")
            return {"success": False, "error": str(e)}

    # ==========================================================
    # Cleanup
    # ==========================================================

    def cleanup_bus_data(self) -> Dict[str, Any]:
        """Remove all bus terminals, schedules, and depots."""
        counts: Dict[str, int] = {}

        for label in ("BusSchedule", "BusDepot", "BusTerminal"):
            count_q = f"MATCH (n:{label}) RETURN count(n) as cnt"
            result = self.execute_query(count_q, {})
            counts[label] = result[0].get("cnt", 0) if result else 0

            delete_q = f"MATCH (n:{label}) DETACH DELETE n"
            self.execute_query(delete_q, {})

        return {
            "success": True,
            "schedules_deleted": counts.get("BusSchedule", 0),
            "depots_deleted": counts.get("BusDepot", 0),
            "terminals_deleted": counts.get("BusTerminal", 0),
        }
