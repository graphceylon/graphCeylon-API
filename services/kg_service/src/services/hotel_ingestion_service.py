"""
Hotel Ingestion Service

Ingests hotels from JSON data into Neo4j knowledge graph with:
- Hotel nodes
- Relationships to attractions (NEAR_ATTRACTION)
- Geographic relationships (LOCATED_IN_DISTRICT, LOCATED_IN_PROVINCE)
- POI nodes and relationships
- Amenity nodes and relationships
- Distance calculations
"""

import json
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from neo4j import GraphDatabase
from pydantic import ValidationError

from core.config import settings
from core.utils import calculate_distance
from models.domain.hotel import (
    HotelCreate,
    HotelIngestionBatch,
    HotelIngestionResult,
    ProximityLevel,
    PriceTier,
    GPSCoordinates,
    NearbyPlace,
    TransportationOption
)


class HotelIngestionService:
    """Service for ingesting hotels into Neo4j"""
    
    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.driver = GraphDatabase.driver(
            uri or settings.neo4j_uri,
            auth=(user or settings.neo4j_user, password or settings.neo4j_password)
        )
    
    def close(self):
        """Close Neo4j connection"""
        self.driver.close()
    
    # ========== Distance Calculations ==========
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points on Earth (km). Delegates to core utility."""
        return calculate_distance(lat1, lon1, lat2, lon2)
    
    @staticmethod
    def get_proximity_level(distance_km: float) -> ProximityLevel:
        """Categorize distance into proximity levels"""
        if distance_km < 2.0:
            return ProximityLevel.VERY_CLOSE
        elif distance_km < 5.0:
            return ProximityLevel.CLOSE
        elif distance_km < 10.0:
            return ProximityLevel.MODERATE
        elif distance_km < 20.0:
            return ProximityLevel.FAR
        else:
            return ProximityLevel.VERY_FAR
    
    @staticmethod
    def generate_hotel_id(hotel_name: str) -> str:
        """Generate unique hotel ID from name"""
        # Remove special characters and convert to lowercase
        hotel_id = hotel_name.lower()
        hotel_id = ''.join(c if c.isalnum() or c.isspace() else '' for c in hotel_id)
        hotel_id = '_'.join(hotel_id.split())
        return f"hotel_{hotel_id}"
    
    # ========== Node Creation ==========
    
    def create_hotel_node(
        self,
        session,
        hotel: HotelCreate,
        attraction_name: str,
        distance_km: float,
        proximity_level: ProximityLevel
    ) -> str:
        """Create Hotel node in Neo4j"""
        hotel_id = self.generate_hotel_id(hotel.name)
        
        # Extract rate as float (remove "US$" prefix if present)
        rate = hotel.rate_per_night
        if isinstance(rate, str):
            rate = float(rate.replace("US$", "").replace("$", "").strip())
        
        query = """
        MERGE (h:Hotel {hotel_id: $hotel_id})
        SET h.name = $name,
            h.type = $type,
            h.description = $description,
            h.link = $link,
            h.latitude = $latitude,
            h.longitude = $longitude,
            h.rate_per_night = $rate_per_night,
            h.total_rate = $total_rate,
            h.currency = $currency,
            h.price_tier = $price_tier,
            h.check_in_time = $check_in_time,
            h.check_out_time = $check_out_time,
            h.rating = $rating,
            h.reviews_count = $reviews_count,
            h.property_token = $property_token,
            h.place_id = $place_id,
            h.serpapi_link = $serpapi_link,
            h.eco_certified = $eco_certified,
            h.distance_to_attraction_km = $distance_km,
            h.proximity_level = $proximity_level,
            h.attraction = $attraction_name,
            h.country = $country,
            h.country_code = $country_code,
            h.province = $province,
            h.district = $district,
            h.city = $city,
            h.town = $town,
            h.postal_code = $postal_code,
            h.formatted_address = $formatted_address,
            h.google_maps_url = $google_maps_url,
            h.coordinates_decimal = $coordinates_decimal,
            h.coordinates_dms = $coordinates_dms,
            h.created_at = datetime(),
            h.updated_at = datetime()
        
        // Belongs to ACCOM domain
        WITH h
        MATCH (d:Domain {code: 'ACCOM'})
        MERGE (h)-[:BELONGS_TO_DOMAIN]->(d)
        
        RETURN h.hotel_id as hotel_id
        """
        
        result = session.run(
            query,
            hotel_id=hotel_id,
            name=hotel.name,
            type=hotel.type.value,
            description=hotel.description,
            link=hotel.link,
            latitude=hotel.gps_coordinates.latitude,
            longitude=hotel.gps_coordinates.longitude,
            rate_per_night=rate,
            total_rate=hotel.total_rate,
            currency=hotel.currency,
            price_tier=hotel.price_tier.value if hotel.price_tier else None,
            check_in_time=hotel.check_in_time,
            check_out_time=hotel.check_out_time,
            rating=hotel.rating,
            reviews_count=hotel.reviews_count,
            property_token=hotel.property_token,
            place_id=hotel.place_id,
            serpapi_link=hotel.serpapi_link,
            eco_certified=hotel.eco_certified,
            distance_km=distance_km,
            proximity_level=proximity_level.value,
            attraction_name=attraction_name,
            country=hotel.country,
            country_code=hotel.country_code,
            province=hotel.province,
            district=hotel.district,
            city=hotel.city,
            town=hotel.town,
            postal_code=hotel.postal_code,
            formatted_address=hotel.formatted_address,
            google_maps_url=hotel.google_maps_url,
            coordinates_decimal=hotel.coordinates_decimal,
            coordinates_dms=hotel.coordinates_dms,
        )
        
        return result.single()["hotel_id"]
    
    def create_amenity_nodes(self, session, hotel_id: str, amenities: List[str]):
        """Create Amenity nodes and link to hotel"""
        if not amenities:
            return
        
        query = """
        UNWIND $amenities AS amenity_name
        MERGE (a:Amenity {name: amenity_name})
        ON CREATE SET a.category = CASE
            WHEN amenity_name IN ['wifi', 'internet'] THEN 'connectivity'
            WHEN amenity_name IN ['pool', 'gym', 'spa'] THEN 'recreation'
            WHEN amenity_name IN ['restaurant', 'bar', 'breakfast'] THEN 'dining'
            WHEN amenity_name IN ['parking', 'shuttle'] THEN 'transport'
            ELSE 'other'
        END
        
        WITH a
        MATCH (h:Hotel {hotel_id: $hotel_id})
        MERGE (h)-[:OFFERS_AMENITY]->(a)
        """
        
        session.run(query, hotel_id=hotel_id, amenities=amenities)
    
    def create_poi_nodes(self, session, hotel_id: str, nearby_places: List[NearbyPlace]):
        """Create Point of Interest nodes from nearby places"""
        if not nearby_places:
            return
        
        pois_created = 0
        
        for poi in nearby_places:
            poi_id = self.generate_hotel_id(poi.name)  # Reuse same ID generation logic
            poi_id = poi_id.replace("hotel_", "poi_")
            
            # Create POI node
            query = """
            MERGE (p:PointOfInterest {poi_id: $poi_id})
            SET p.name = $name,
                p.category = $category,
                p.rating = $rating,
                p.reviews = $reviews,
                p.description = $description,
                p.link = $link,
                p.thumbnail = $thumbnail,
                p.latitude = $latitude,
                p.longitude = $longitude,
                p.updated_at = datetime()
            
            WITH p
            MATCH (h:Hotel {hotel_id: $hotel_id})
            MERGE (h)-[r:NEARBY_POI]->(p)
            SET r.category = $category
            """
            
            session.run(
                query,
                poi_id=poi_id,
                hotel_id=hotel_id,
                name=poi.name,
                category=poi.category,
                rating=poi.rating,
                reviews=poi.reviews,
                description=poi.description,
                link=poi.link,
                thumbnail=poi.thumbnail,
                latitude=poi.gps_coordinates.latitude if poi.gps_coordinates else None,
                longitude=poi.gps_coordinates.longitude if poi.gps_coordinates else None
            )
            
            # Create transportation relationships
            if poi.transportations:
                for transport in poi.transportations:
                    transport_query = """
                    MATCH (h:Hotel {hotel_id: $hotel_id})
                    MATCH (p:PointOfInterest {poi_id: $poi_id})
                    MERGE (h)-[r:ACCESSIBLE_VIA {type: $transport_type}]->(p)
                    SET r.duration = $duration,
                        r.duration_minutes = $duration_minutes,
                        r.cost_estimate = $cost_estimate
                    """
                    
                    session.run(
                        transport_query,
                        hotel_id=hotel_id,
                        poi_id=poi_id,
                        transport_type=transport.type.lower(),
                        duration=transport.duration,
                        duration_minutes=transport.duration_minutes,
                        cost_estimate=transport.cost_estimate
                    )
            
            pois_created += 1
        
        return pois_created
    
    # ========== Relationship Creation ==========
    
    def create_hotel_attraction_relationship(
        self,
        session,
        hotel_id: str,
        attraction_name: str,
        distance_km: float,
        proximity_level: ProximityLevel,
        travel_time_taxi: Optional[int] = None,
        travel_time_public: Optional[int] = None
    ):
        """Create NEAR_ATTRACTION relationship"""
        query = """
        MATCH (h:Hotel {hotel_id: $hotel_id})
        MATCH (a:Attraction)
        WHERE a.title = $attraction_name OR a.name = $attraction_name
        MERGE (h)-[r:NEAR_ATTRACTION]->(a)
        SET r.distance_km = $distance_km,
            r.proximity_level = $proximity_level,
            r.travel_time_taxi = $travel_time_taxi,
            r.travel_time_public = $travel_time_public,
            r.confidence = 1.0,
            r.source = 'google_hotels',
            r.created_at = datetime()
        
        RETURN a.title as attraction_title
        """
        
        result = session.run(
            query,
            hotel_id=hotel_id,
            attraction_name=attraction_name,
            distance_km=distance_km,
            proximity_level=proximity_level.value,
            travel_time_taxi=travel_time_taxi,
            travel_time_public=travel_time_public
        )
        
        return result.single() is not None
    
    def link_hotel_to_geography(self, session, hotel_id: str, hotel: HotelCreate):
        """Link hotel to District and Province nodes using stored administrative_areas data"""
        
        # Primary: use district/province extracted directly from geolocation
        if hotel.district or hotel.province:
            query = """
            MATCH (h:Hotel {hotel_id: $hotel_id})
            
            // Match district by name (case-insensitive)
            OPTIONAL MATCH (d:District)
            WHERE $district IS NOT NULL AND toLower(d.name) = toLower($district)
            
            WITH h, d
            FOREACH (_ IN CASE WHEN d IS NOT NULL THEN [1] ELSE [] END |
                MERGE (h)-[:LOCATED_IN_DISTRICT]->(d)
            )
            
            // Match province either via district relationship or by name directly
            WITH h, d
            OPTIONAL MATCH (p:Province)
            WHERE $province IS NOT NULL AND toLower(p.name) = toLower($province)
            
            WITH h, d, p
            FOREACH (_ IN CASE WHEN p IS NOT NULL THEN [1] ELSE [] END |
                MERGE (h)-[:LOCATED_IN_PROVINCE]->(p)
            )
            
            RETURN d.name as district, p.name as province
            """
            
            result = session.run(
                query,
                hotel_id=hotel_id,
                district=hotel.district,
                province=hotel.province
            )
            record = result.single()
            if record and (record["district"] or record["province"]):
                return record
        
        # Fallback: derive geography via the associated attraction
        fallback_query = """
        MATCH (h:Hotel {hotel_id: $hotel_id})
        
        OPTIONAL MATCH (a:Attraction)-[:LOCATED_IN]->(d:District)
        WHERE a.title = $attraction_name OR a.name = $attraction_name
        
        WITH h, d
        WHERE d IS NOT NULL
        MERGE (h)-[:LOCATED_IN_DISTRICT]->(d)
        
        WITH h, d
        OPTIONAL MATCH (d)-[:HAS_DISTRICT]-(p:Province)
        WHERE p IS NOT NULL
        MERGE (h)-[:LOCATED_IN_PROVINCE]->(p)
        
        RETURN d.name as district, p.name as province
        """
        
        result = session.run(
            fallback_query,
            hotel_id=hotel_id,
            attraction_name=hotel.attraction_name
        )
        record = result.single()
        return record if record else None
    
    # ========== Main Ingestion Logic ==========
    
    def get_attraction_coordinates(self, session, attraction_name: str) -> Optional[Tuple[float, float]]:
        """Get attraction coordinates from database"""
        query = """
        MATCH (a:Attraction)
        WHERE a.title = $attraction_name OR a.name = $attraction_name
        RETURN a.latitude as lat, a.longitude as lon
        """
        
        result = session.run(query, attraction_name=attraction_name)
        record = result.single()
        
        if record and record["lat"] and record["lon"]:
            return (record["lat"], record["lon"])
        return None
    
    def ingest_hotel(
        self,
        session,
        hotel: HotelCreate,
        attraction_name: str,
        attraction_coords: Tuple[float, float]
    ) -> Dict[str, Any]:
        """Ingest single hotel with all relationships"""
        result = {
            "hotel_id": None,
            "relationships": 0,
            "pois": 0,
            "amenities": 0,
            "error": None
        }
        
        try:
            # Calculate distance to attraction
            distance_km = self.haversine_distance(
                hotel.gps_coordinates.latitude,
                hotel.gps_coordinates.longitude,
                attraction_coords[0],
                attraction_coords[1]
            )
            
            proximity_level = self.get_proximity_level(distance_km)
            
            # Create hotel node
            hotel_id = self.create_hotel_node(
                session,
                hotel,
                attraction_name,
                distance_km,
                proximity_level
            )
            result["hotel_id"] = hotel_id
            
            # Create hotel-attraction relationship
            if self.create_hotel_attraction_relationship(
                session,
                hotel_id,
                attraction_name,
                distance_km,
                proximity_level
            ):
                result["relationships"] += 1
            
            # Link to geography
            self.link_hotel_to_geography(session, hotel_id, hotel)
            result["relationships"] += 1
            
            # Create amenities
            if hotel.amenities:
                self.create_amenity_nodes(session, hotel_id, hotel.amenities)
                result["amenities"] = len(hotel.amenities)
                result["relationships"] += len(hotel.amenities)
            
            # Create POIs
            if hotel.nearby_places:
                pois_created = self.create_poi_nodes(session, hotel_id, hotel.nearby_places)
                result["pois"] = pois_created or 0
                result["relationships"] += result["pois"]
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def ingest_batch(self, batch: HotelIngestionBatch) -> HotelIngestionResult:
        """Ingest batch of hotels for one attraction"""
        start_time = time.time()
        
        result = HotelIngestionResult(
            success=False,
            processing_time_seconds=0
        )
        
        with self.driver.session() as session:
            # Get attraction coordinates
            attraction_coords = self.get_attraction_coordinates(
                session,
                batch.attraction_name
            )
            
            if not attraction_coords:
                result.errors.append(
                    f"Attraction '{batch.attraction_name}' not found in database"
                )
                result.processing_time_seconds = time.time() - start_time
                return result
            
            # Ingest each hotel
            for hotel in batch.hotels:
                hotel_result = self.ingest_hotel(
                    session,
                    hotel,
                    batch.attraction_name,
                    attraction_coords
                )
                
                if hotel_result["error"]:
                    result.errors.append(
                        f"Hotel '{hotel.name}': {hotel_result['error']}"
                    )
                else:
                    result.hotels_created += 1
                    result.relationships_created += hotel_result["relationships"]
                    result.pois_created += hotel_result["pois"]
                    result.amenities_created += hotel_result["amenities"]
        
        result.success = result.hotels_created > 0
        result.processing_time_seconds = time.time() - start_time
        
        return result
    
    def ingest_from_json_file(self, json_file_path: str) -> Dict[str, Any]:
        """Ingest all hotels from JSON file"""
        overall_start = time.time()
        
        # Load JSON
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        total_results = {
            "total_attractions": 0,
            "total_hotels_created": 0,
            "total_relationships": 0,
            "total_pois": 0,
            "total_amenities": 0,
            "total_errors": 0,
            "attraction_results": []
        }
        
        # Process each attraction
        for attraction_data in data.get("attractions", []):
            attraction_name = attraction_data.get("attraction")
            if not attraction_name or not attraction_data.get("hotels"):
                continue
            
            print(f"\n{'='*80}")
            print(f"Processing: {attraction_name}")
            print(f"{'='*80}")
            
            # Extract geolocation data from the attraction's geolocation block
            geolocation = attraction_data.get("geolocation", {}) or {}
            address_info = geolocation.get("address_info", {}) or {}
            admin_areas = address_info.get("administrative_areas", {}) or {}
            map_links = geolocation.get("map_links", {}) or {}

            attraction_country = admin_areas.get("country")
            attraction_country_code = admin_areas.get("country_code")
            attraction_province = admin_areas.get("province")
            attraction_district = admin_areas.get("district")
            attraction_city = admin_areas.get("city") or admin_areas.get("town")
            attraction_town = admin_areas.get("town")
            attraction_postal_code = admin_areas.get("postal_code")
            attraction_formatted_address = address_info.get("formatted_address")
            attraction_google_maps_url = map_links.get("google_maps_url")
            attraction_coordinates_decimal = map_links.get("coordinates_decimal")
            attraction_coordinates_dms = map_links.get("coordinates_dms")

            # Convert to HotelCreate models
            hotels = []
            for hotel_data in attraction_data.get("hotels", []):
                try:
                    # Parse nearby places
                    nearby_places = []
                    for place_data in hotel_data.get("nearby_places", []):
                        # Parse transportations
                        transportations = []
                        for trans_data in place_data.get("transportations", []):
                            transportations.append(
                                TransportationOption(**trans_data)
                            )
                        
                        # Parse GPS coordinates
                        gps = place_data.get("gps_coordinates")
                        gps_coords = None
                        if gps:
                            gps_coords = GPSCoordinates(**gps)
                        
                        nearby_places.append(
                            NearbyPlace(
                                **{**place_data, "transportations": transportations, "gps_coordinates": gps_coords}
                            )
                        )
                    
                    # Create hotel — populate all geo fields from attraction's geolocation block
                    hotel = HotelCreate(
                        name=hotel_data.get("name"),
                        description=hotel_data.get("description"),
                        link=hotel_data.get("link"),
                        gps_coordinates=GPSCoordinates(**hotel_data.get("gps_coordinates", {})),
                        rate_per_night=hotel_data.get("rate_per_night"),
                        total_rate=hotel_data.get("total_rate"),
                        check_in_time=hotel_data.get("check_in_time"),
                        check_out_time=hotel_data.get("check_out_time"),
                        property_token=hotel_data.get("property_token"),
                        serpapi_link=hotel_data.get("serpapi_property_details_link"),
                        rating=hotel_data.get("rating"),
                        reviews_count=hotel_data.get("reviews"),
                        images=hotel_data.get("images", []),
                        amenities=hotel_data.get("amenities", []),
                        nearby_places=nearby_places,
                        attraction_name=attraction_name,
                        # Authoritative geo fields from administrative_areas
                        country=attraction_country,
                        country_code=attraction_country_code,
                        province=attraction_province,
                        district=attraction_district,
                        city=attraction_city,
                        town=attraction_town,
                        postal_code=attraction_postal_code,
                        formatted_address=attraction_formatted_address,
                        google_maps_url=attraction_google_maps_url,
                        coordinates_decimal=attraction_coordinates_decimal,
                        coordinates_dms=attraction_coordinates_dms,
                    )
                    hotels.append(hotel)
                    
                except ValidationError as e:
                    print(f"  ⚠️  Validation error for hotel '{hotel_data.get('name')}': {e}")
                    total_results["total_errors"] += 1
                except Exception as e:
                    print(f"  ⚠️  Error parsing hotel '{hotel_data.get('name')}': {e}")
                    total_results["total_errors"] += 1
            
            if not hotels:
                print(f"  ⚠️  No valid hotels found for {attraction_name}")
                continue
            
            # Create batch
            batch = HotelIngestionBatch(
                attraction_name=attraction_name,
                attraction_description=attraction_data.get("attraction_description"),
                attraction_geolocation=attraction_data.get("geolocation"),
                hotel_count=len(hotels),
                hotels=hotels,
                metadata=data.get("scrape_metadata", {})
            )
            
            # Ingest batch
            batch_result = self.ingest_batch(batch)
            
            # Report
            print(f"\n  ✓ Hotels created: {batch_result.hotels_created}/{len(hotels)}")
            print(f"  ✓ Relationships: {batch_result.relationships_created}")
            print(f"  ✓ POIs: {batch_result.pois_created}")
            print(f"  ✓ Amenities: {batch_result.amenities_created}")
            print(f"  ✓ Time: {batch_result.processing_time_seconds:.2f}s")
            
            if batch_result.errors:
                print(f"  ⚠️  Errors: {len(batch_result.errors)}")
                for error in batch_result.errors[:3]:  # Show first 3
                    print(f"     - {error}")
            
            # Aggregate
            total_results["total_attractions"] += 1
            total_results["total_hotels_created"] += batch_result.hotels_created
            total_results["total_relationships"] += batch_result.relationships_created
            total_results["total_pois"] += batch_result.pois_created
            total_results["total_amenities"] += batch_result.amenities_created
            total_results["total_errors"] += len(batch_result.errors)
            
            total_results["attraction_results"].append({
                "attraction": attraction_name,
                "hotels_created": batch_result.hotels_created,
                "relationships": batch_result.relationships_created
            })
        
        total_results["total_time_seconds"] = time.time() - overall_start
        
        return total_results


def main():
    """Main ingestion script"""
    import sys
    
    print("="*80)
    print("HOTEL INGESTION SERVICE")
    print("="*80)
    
    # Default path
    json_file = "data/kg_service/data/hotels.json"
    
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    
    json_path = Path(json_file)
    
    if not json_path.exists():
        print(f"❌ Error: File not found: {json_file}")
        sys.exit(1)
    
    print(f"\n📁 Loading: {json_path}")
    print(f"🔗 Connecting to Neo4j: {settings.neo4j_uri}")
    
    # Initialize service
    service = HotelIngestionService()
    
    try:
        # Ingest
        results = service.ingest_from_json_file(str(json_path))
        
        # Final report
        print("\n" + "="*80)
        print("INGESTION COMPLETE")
        print("="*80)
        print(f"\n📊 Total Attractions Processed: {results['total_attractions']}")
        print(f"🏨 Total Hotels Created: {results['total_hotels_created']}")
        print(f"🔗 Total Relationships: {results['total_relationships']}")
        print(f"📍 Total POIs: {results['total_pois']}")
        print(f"🎯 Total Amenities: {results['total_amenities']}")
        print(f"⚠️  Total Errors: {results['total_errors']}")
        print(f"⏱️  Total Time: {results['total_time_seconds']:.2f}s")
        
        print("\n✅ Hotels successfully ingested into Neo4j!")
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        service.close()


if __name__ == "__main__":
    main()
