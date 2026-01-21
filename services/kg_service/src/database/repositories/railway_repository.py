"""
Railway Repository

Database operations for railway stations and train schedules
Handles Cypher queries for the Transportation Domain (Domain 4)
"""

import logging
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from neo4j import Driver

from .base import BaseRepository

logger = logging.getLogger(__name__)


class RailwayRepository(BaseRepository):
    """Repository for railway stations and train schedule operations."""
    
    def __init__(self, driver: Driver):
        super().__init__(driver)
        self.domain_name = "Transportation"
        self.domain_code = "TRANS"
    
    # ========== Railway Station Operations ==========
    
    def create_railway_station(self, station_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a railway station node in the knowledge graph."""
        cypher = """
        // Get Transportation Domain
        MATCH (domain:Domain {name: $domain_name})
        
        // Create Railway Station node
        CREATE (station:RailwayStation:TransportationInfrastructure)
        SET station.name = $name,
            station.station_id = $station_id,
            station.enriched = $enriched,
            station.is_major_station = $is_major_station,
            station.platform_count = $platform_count,
            station.contact_number = $contact_number,
            station.facilities = $facilities,
            station.alternative_names = $alternative_names,
            station.created_at = datetime(),
            station.enriched_at = $enriched_at,
            station.geolocation_json = $geolocation_json,
            station.google_place_data_json = $google_place_data_json
        
        // Set geolocation if available
        WITH station, domain
        FOREACH (coord IN CASE WHEN $latitude IS NOT NULL THEN [1] ELSE [] END |
            SET station.latitude = $latitude,
                station.longitude = $longitude,
                station.coordinates_accuracy = $coordinates_accuracy
        )
        
        // Set administrative areas
        FOREACH (prov IN CASE WHEN $province IS NOT NULL THEN [1] ELSE [] END |
            SET station.province = $province
        )
        FOREACH (dist IN CASE WHEN $district IS NOT NULL THEN [1] ELSE [] END |
            SET station.district = $district
        )
        FOREACH (city IN CASE WHEN $city IS NOT NULL THEN [1] ELSE [] END |
            SET station.city = $city
        )
        
        // Set Google Place data
        WITH station, domain
        FOREACH (rating IN CASE WHEN $google_rating IS NOT NULL THEN [1] ELSE [] END |
            SET station.google_rating = $google_rating,
                station.google_ratings_total = $google_ratings_total,
                station.google_place_url = $google_place_url,
                station.google_place_id = $google_place_id
        )
        
        // Link to domain
        CREATE (station)-[:BELONGS_TO_DOMAIN]->(domain)
        
        // Link to Province if exists
        WITH station
        OPTIONAL MATCH (prov:Province {name: station.province})
        FOREACH (_ IN CASE WHEN prov IS NOT NULL THEN [1] ELSE [] END |
            MERGE (station)-[:LOCATED_IN_PROVINCE]->(prov)
        )
        
        // Link to District if exists
        WITH station
        OPTIONAL MATCH (dist:District {name: station.district})
        FOREACH (_ IN CASE WHEN dist IS NOT NULL THEN [1] ELSE [] END |
            MERGE (station)-[:LOCATED_IN_DISTRICT]->(dist)
        )
        
        RETURN station
        """
        
        # Extract nested data for parameters
        params = {
            "domain_name": self.domain_name,
            "name": station_data.get("name"),
            "station_id": station_data.get("station_id") or station_data.get("name", "").replace(" ", "_").upper(),
            "enriched": station_data.get("enriched", False),
            "is_major_station": station_data.get("is_major_station", False),
            "platform_count": station_data.get("platform_count"),
            "contact_number": station_data.get("contact_number"),
            "facilities": station_data.get("facilities", []),
            "alternative_names": station_data.get("alternative_names", []),
            "enriched_at": station_data.get("enriched_at"),
        }
        
        # Extract geolocation
        geolocation = station_data.get("geolocation", {})
        coordinates = geolocation.get("coordinates", {})
        address_info = geolocation.get("address_info", {})
        admin_areas = address_info.get("administrative_areas", {})
        geocoding_meta = geolocation.get("geocoding_metadata", {})
        
        params.update({
            "latitude": coordinates.get("latitude"),
            "longitude": coordinates.get("longitude"),
            "coordinates_accuracy": coordinates.get("accuracy"),
            "province": admin_areas.get("province"),
            "district": admin_areas.get("district"),
            "city": admin_areas.get("city"),
        })
        
        # Extract Google Place data
        google_data = station_data.get("google_place_data", {})
        params.update({
            "google_rating": google_data.get("rating"),
            "google_ratings_total": google_data.get("user_ratings_total"),
            "google_place_url": google_data.get("place_url"),
            "google_place_id": geocoding_meta.get("place_id"),
            "geolocation_json": json.dumps(geolocation) if geolocation else None,
            "google_place_data_json": json.dumps(google_data) if google_data else None,
        })
        
        result = self.execute_query(cypher, params)
        return result[0] if result else {}
    
    def get_railway_stations(
        self,
        province: Optional[str] = None,
        district: Optional[str] = None,
        name_pattern: Optional[str] = None,
        is_major: Optional[bool] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Query railway stations with filters."""
        cypher = """
        MATCH (station:RailwayStation)
        WHERE 1=1
        {province_filter}
        {district_filter}
        {name_filter}
        {major_filter}
        RETURN properties(station) as station
        ORDER BY station.name
        LIMIT $limit
        """
        
        # Build dynamic filters
        filters = {
            "province_filter": "AND station.province = $province" if province else "",
            "district_filter": "AND station.district = $district" if district else "",
            "name_filter": "AND toLower(station.name) CONTAINS toLower($name_pattern)" if name_pattern else "",
            "major_filter": "AND station.is_major_station = $is_major" if is_major is not None else "",
        }
        
        cypher = cypher.format(**filters)
        
        params = {
            "limit": limit,
            "province": province,
            "district": district,
            "name_pattern": name_pattern,
            "is_major": is_major,
        }
        
        return self.execute_query(cypher, params)
    
    def get_station_by_name(self, station_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific railway station by name."""
        cypher = """
        MATCH (station:RailwayStation)
        WHERE toLower(station.name) = toLower($station_name)
        RETURN properties(station) as station
        LIMIT 1
        """
        
        result = self.execute_query(cypher, {"station_name": station_name})
        return result[0] if result else None
    
    def get_stations_by_province(self, province: str) -> List[Dict[str, Any]]:
        """Get all railway stations in a province."""
        return self.get_railway_stations(province=province, limit=200)
    
    def get_stations_by_district(self, district: str) -> List[Dict[str, Any]]:
        """Get all railway stations in a district."""
        return self.get_railway_stations(district=district, limit=200)
    
    # ========== Train Schedule Operations ==========
    
    def create_train_schedule(self, schedule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a train schedule and connect stations."""
        cypher = """
        // Get Transportation Domain
        MATCH (domain:Domain {name: $domain_name})
        
        // Match start and end stations
        MATCH (start:RailwayStation)
        WHERE toLower(start.name) = toLower($start_station)
        
        MATCH (end:RailwayStation)
        WHERE toLower(end.name) = toLower($end_station)
        
        // Create Train Schedule node
        CREATE (schedule:TrainSchedule:TransportationService)
        SET schedule.schedule_id = $schedule_id,
            schedule.schedule_date = $schedule_date,
            schedule.departure_time = $departure_time,
            schedule.arrival_time = $arrival_time,
            schedule.duration = $duration,
            schedule.train_number = $train_number,
            schedule.train_type = $train_type,
            schedule.distance = $distance,
            schedule.distance_km = $distance_km,
            schedule.train_stops = $train_stops,
            schedule.ends_at = $ends_at,
            schedule.price_2nd_class = $price_2nd_class,
            schedule.price_3rd_class = $price_3rd_class,
            schedule.start_contact = $start_contact,
            schedule.end_contact = $end_contact,
            schedule.first_train_time = $first_train_time,
            schedule.last_train_time = $last_train_time,
            schedule.daily_train_count = $daily_train_count,
            schedule.created_at = datetime()
        
        // Create relationships
        CREATE (schedule)-[:DEPARTS_FROM]->(start)
        CREATE (schedule)-[:ARRIVES_AT]->(end)
        CREATE (schedule)-[:BELONGS_TO_DOMAIN]->(domain)
        
        // Create CONNECTS relationship between stations
        MERGE (start)-[r:CONNECTED_BY_TRAIN]->(end)
        ON CREATE SET r.created_at = datetime(), r.route_count = 1
        ON MATCH SET r.route_count = r.route_count + 1, r.updated_at = datetime()
        
        RETURN schedule, start, end
        """
        
        # Parse distance
        distance_km = None
        distance_str = schedule_data.get("distance", "")
        if distance_str:
            try:
                distance_km = float(distance_str.replace("km", "").strip())
            except (ValueError, AttributeError):
                pass
        
        params = {
            "domain_name": self.domain_name,
            "schedule_id": schedule_data.get("schedule_id") or f"{schedule_data['train_number']}_{schedule_data['schedule_date']}",
            "schedule_date": schedule_data.get("schedule_date"),
            "start_station": schedule_data.get("start_station"),
            "end_station": schedule_data.get("end_station"),
            "departure_time": schedule_data.get("departure_time"),
            "arrival_time": schedule_data.get("arrival_time"),
            "duration": schedule_data.get("duration"),
            "train_number": schedule_data.get("train_number"),
            "train_type": schedule_data.get("train_type"),
            "distance": distance_str,
            "distance_km": distance_km,
            "train_stops": schedule_data.get("train_stops"),
            "ends_at": schedule_data.get("ends_at"),
            "price_2nd_class": schedule_data.get("price_2nd_class"),
            "price_3rd_class": schedule_data.get("price_3rd_class"),
            "start_contact": schedule_data.get("start_contact"),
            "end_contact": schedule_data.get("end_contact"),
            "first_train_time": schedule_data.get("first_train_time"),
            "last_train_time": schedule_data.get("last_train_time"),
            "daily_train_count": schedule_data.get("daily_train_count"),
        }
        
        result = self.execute_query(cypher, params)
        return result[0] if result else {}
    
    def get_train_schedules(
        self,
        start_station: Optional[str] = None,
        end_station: Optional[str] = None,
        schedule_date: Optional[str] = None,
        train_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Query train schedules with filters."""
        cypher = """
        MATCH (schedule:TrainSchedule)-[:DEPARTS_FROM]->(start:RailwayStation)
        MATCH (schedule)-[:ARRIVES_AT]->(end:RailwayStation)
        WHERE 1=1
        {start_filter}
        {end_filter}
        {date_filter}
        {type_filter}
        RETURN properties(schedule) as schedule, start.name as start_station, end.name as end_station
        ORDER BY schedule.departure_time
        LIMIT $limit
        """
        
        # Build dynamic filters
        filters = {
            "start_filter": "AND toLower(start.name) = toLower($start_station)" if start_station else "",
            "end_filter": "AND toLower(end.name) = toLower($end_station)" if end_station else "",
            "date_filter": "AND schedule.schedule_date = $schedule_date" if schedule_date else "",
            "type_filter": "AND schedule.train_type = $train_type" if train_type else "",
        }
        
        cypher = cypher.format(**filters)
        
        params = {
            "limit": limit,
            "start_station": start_station,
            "end_station": end_station,
            "schedule_date": schedule_date,
            "train_type": train_type,
        }
        
        results = self.execute_query(cypher, params)
        
        # Add station names to schedule properties
        for result in results:
            if 'schedule' in result:
                result['schedule']['start_station'] = result.get('start_station')
                result['schedule']['end_station'] = result.get('end_station')
        
        return [r.get("schedule", {}) for r in results]
    
    def find_routes_between_stations(
        self,
        start_station: str,
        end_station: str,
        max_transfers: int = 2
    ) -> List[Dict[str, Any]]:
        """Find possible routes between two stations (including transfers)."""
        # For direct routes
        if max_transfers == 0:
            cypher = """
            MATCH (start:RailwayStation)<-[:DEPARTS_FROM]-(schedule:TrainSchedule)-[:ARRIVES_AT]->(end:RailwayStation)
            WHERE toLower(start.name) = toLower($start_station)
            AND toLower(end.name) = toLower($end_station)
            RETURN properties(schedule) as schedule, 
                   start.name as start_station, 
                   end.name as end_station
            ORDER BY schedule.departure_time
            LIMIT 10
            """
        else:
            # For routes with transfers, use path finding
            cypher = """
            MATCH path = (start:RailwayStation)-[:CONNECTED_BY_TRAIN*1..3]-(end:RailwayStation)
            WHERE toLower(start.name) = toLower($start_station)
            AND toLower(end.name) = toLower($end_station)
            AND length(path) <= $max_hops
            RETURN path
            LIMIT 5
            """
        
        params = {
            "start_station": start_station,
            "end_station": end_station,
            "max_hops": max_transfers + 1,
        }
        
        return self.execute_query(cypher, params)
    
    # ========== Statistics ==========
    
    def get_station_statistics(self) -> Dict[str, Any]:
        """Get statistics about railway stations."""
        cypher = """
        // Get overall counts
        MATCH (station:RailwayStation)
        WITH 
            count(station) as total_stations,
            sum(CASE WHEN station.enriched = true THEN 1 ELSE 0 END) as enriched_count,
            sum(CASE WHEN station.is_major_station = true THEN 1 ELSE 0 END) as major_count
        
        // Get province counts in subquery
        CALL {
            MATCH (s:RailwayStation)
            WHERE s.province IS NOT NULL
            WITH s.province as province, count(s) as province_count
            ORDER BY province_count DESC
            RETURN collect({province: province, count: province_count}) as province_stats
        }
        
        // Get district counts in subquery
        CALL {
            MATCH (s:RailwayStation)
            WHERE s.district IS NOT NULL
            WITH s.district as district, count(s) as district_count
            ORDER BY district_count DESC
            RETURN collect({district: district, count: district_count}) as district_stats
        }
        
        RETURN {
            total_stations: total_stations,
            enriched_stations: enriched_count,
            major_stations: major_count,
            stations_by_province: province_stats,
            stations_by_district: district_stats
        } as statistics
        """
        
        result = self.execute_query(cypher, {})
        return result[0].get("statistics", {}) if result else {}
    
    def get_schedule_statistics(self) -> Dict[str, Any]:
        """Get statistics about train schedules."""
        cypher = """
        MATCH (schedule:TrainSchedule)
        WITH 
            count(schedule) as total_schedules,
            count(DISTINCT schedule.train_number) as unique_trains,
            collect(DISTINCT schedule.train_type) as train_types,
            min(schedule.schedule_date) as earliest_date,
            max(schedule.schedule_date) as latest_date
        
        // Count by train type
        UNWIND train_types as train_type
        OPTIONAL MATCH (s:TrainSchedule {train_type: train_type})
        WITH total_schedules, unique_trains, earliest_date, latest_date,
             train_type, count(s) as type_count
        
        // Count unique routes
        MATCH (schedule:TrainSchedule)-[:DEPARTS_FROM]->(start:RailwayStation)
        MATCH (schedule)-[:ARRIVES_AT]->(end:RailwayStation)
        WITH total_schedules, unique_trains, earliest_date, latest_date,
             collect({type: train_type, count: type_count}) as type_stats,
             count(DISTINCT start.name + '->' + end.name) as unique_routes
        
        RETURN {
            total_schedules: total_schedules,
            unique_trains: unique_trains,
            unique_routes: unique_routes,
            schedules_by_train_type: type_stats,
            date_range: {
                earliest: earliest_date,
                latest: latest_date
            }
        } as statistics
        """
        
        result = self.execute_query(cypher, {})
        return result[0].get("statistics", {}) if result else {}
    
    # ========== Bulk Loading ==========
    
    def load_stations_from_json(self, json_file_path: str) -> Dict[str, Any]:
        """Bulk load railway stations from JSON file."""
        try:
            file_path = Path(json_file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"JSON file not found: {json_file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            stations = data.get("stations", [])
            total = len(stations)
            created = 0
            errors = []
            
            logger.info(f"Loading {total} railway stations from {json_file_path}")
            
            for idx, station in enumerate(stations):
                try:
                    self.create_railway_station(station)
                    created += 1
                    if (idx + 1) % 50 == 0:
                        logger.info(f"Loaded {idx + 1}/{total} stations...")
                except Exception as e:
                    logger.error(f"Error loading station {station.get('name', 'Unknown')}: {e}")
                    errors.append({"station": station.get("name"), "error": str(e)})
            
            logger.info(f"Completed loading {created}/{total} railway stations")
            
            return {
                "success": True,
                "total": total,
                "created": created,
                "failed": len(errors),
                "errors": errors[:10]  # Return first 10 errors
            }
            
        except Exception as e:
            logger.error(f"Failed to load stations from JSON: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def load_schedules_from_csv(self, csv_file_path: str) -> Dict[str, Any]:
        """Bulk load train schedules from CSV file."""
        try:
            import csv
            
            file_path = Path(csv_file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"CSV file not found: {csv_file_path}")
            
            created = 0
            errors = []
            
            logger.info(f"Loading train schedules from {csv_file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                total = len(rows)
                
                for idx, row in enumerate(rows):
                    try:
                        # Check if stations exist
                        start_exists = self.get_station_by_name(row['start_station'])
                        end_exists = self.get_station_by_name(row['end_station'])
                        
                        if not start_exists or not end_exists:
                            logger.warning(f"Skipping schedule - station not found: {row['start_station']} -> {row['end_station']}")
                            continue
                        
                        self.create_train_schedule(row)
                        created += 1
                        if (idx + 1) % 100 == 0:
                            logger.info(f"Loaded {idx + 1}/{total} schedules...")
                    except Exception as e:
                        logger.error(f"Error loading schedule {row.get('train_number', 'Unknown')}: {e}")
                        errors.append({"train_number": row.get("train_number"), "error": str(e)})
            
            logger.info(f"Completed loading {created}/{total} train schedules")
            
            return {
                "success": True,
                "total": total,
                "created": created,
                "failed": len(errors),
                "errors": errors[:10]
            }
            
        except Exception as e:
            logger.error(f"Failed to load schedules from CSV: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def cleanup_railway_data(self) -> Dict[str, Any]:
        """Remove all railway stations and schedules."""
        # First count schedules
        count_schedules = """
        MATCH (schedule:TrainSchedule)
        RETURN count(schedule) as schedules_count
        """
        
        # Then count stations
        count_stations = """
        MATCH (station:RailwayStation)
        RETURN count(station) as stations_count
        """
        
        # Get counts
        schedules_result = self.execute_query(count_schedules, {})
        stations_result = self.execute_query(count_stations, {})
        
        schedules_count = schedules_result[0].get("schedules_count", 0) if schedules_result else 0
        stations_count = stations_result[0].get("stations_count", 0) if stations_result else 0
        
        # Delete schedules
        delete_schedules = """
        MATCH (schedule:TrainSchedule)
        DETACH DELETE schedule
        """
        
        # Delete stations
        delete_stations = """
        MATCH (station:RailwayStation)
        DETACH DELETE station
        """
        
        self.execute_query(delete_schedules, {})
        self.execute_query(delete_stations, {})
        
        return {
            "success": True,
            "schedules_deleted": schedules_count,
            "stations_deleted": stations_count
        }
