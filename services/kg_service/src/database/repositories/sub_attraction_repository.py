"""Repository for sub-attraction (POI) database operations.

Manages SubAttraction and POIGroup nodes in Neo4j, including:
- Schema initialization (constraints + indexes)
- Bulk loading from JSON files (sub-attractions directory)
- Relationship creation to Attraction, District, Province, POIGroup, Hotel
- Querying with dynamic filters
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from neo4j import Driver

from .base import BaseRepository
from ..utils import DatabasePaths

logger = logging.getLogger(__name__)

# POI groups that map to meaningful tourism categories
VALID_POI_GROUPS = {
    "Shopping & City",
    "Food & Markets",
    "Religious / Spiritual",
    "Culture & Heritage",
    "Adventure & Hiking",
    "Nature & Eco",
}


class SubAttractionRepository(BaseRepository):
    """Repository for managing sub-attraction (POI) data in Neo4j."""

    def __init__(self, driver: Driver):
        super().__init__(driver)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def load_schema(self) -> Dict[str, Any]:
        """Load sub-attraction schema (constraints and indexes)."""
        return self.load_schema_from_file("init_sub_attractions_schema.cypher")

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def load_from_directory(self, dir_path: str = None) -> Dict[str, Any]:
        """Load all sub-attraction JSON files from a directory.

        Each JSON file represents POIs for one parent attraction location.

        Args:
            dir_path: Optional path to directory. Defaults to data/sub-attractions.

        Returns:
            Dictionary with success status and statistics.
        """
        try:
            if dir_path is None:
                dir_path = str(DatabasePaths.get_data_directory() / "sub-attractions")

            data_dir = Path(dir_path)
            if not data_dir.exists():
                raise FileNotFoundError(f"Sub-attractions directory not found: {data_dir}")

            json_files = sorted(data_dir.glob("*.json"))
            if not json_files:
                return {
                    "success": True,
                    "message": "No JSON files found in sub-attractions directory",
                    "locations_processed": 0,
                }

            logger.info(f"Found {len(json_files)} sub-attraction files to process")

            total_created = 0
            total_groups = 0
            total_relationships = 0
            total_hotel_links = 0
            errors: List[str] = []

            # Pre-create POIGroup nodes
            groups_created = self._ensure_poi_groups()
            total_groups = groups_created

            for json_file in json_files:
                try:
                    result = self._load_single_file(json_file)
                    total_created += result["sub_attractions_created"]
                    total_relationships += result["relationships_created"]
                except Exception as e:
                    error_msg = f"Failed to process {json_file.name}: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            # Create hotel proximity links after all sub-attractions are loaded
            try:
                total_hotel_links = self._create_hotel_links()
            except Exception as e:
                logger.warning(f"Failed to create hotel links: {e}")
                errors.append(f"Hotel link creation failed: {e}")

            stats = self.get_statistics()

            return {
                "success": True,
                "message": f"Loaded sub-attractions from {len(json_files)} files",
                "locations_processed": len(json_files),
                "sub_attractions_created": total_created,
                "groups_created": total_groups,
                "relationships_created": total_relationships,
                "hotel_links_created": total_hotel_links,
                "errors": errors,
                "statistics": stats,
            }

        except Exception as e:
            logger.error(f"Failed to load sub-attractions: {e}")
            raise

    def _ensure_poi_groups(self) -> int:
        """Create POIGroup nodes for all known groups.

        Returns:
            Number of groups created or merged.
        """
        cypher = """
        UNWIND $groups AS group_name
        MERGE (g:POIGroup {name: group_name})
        ON CREATE SET g.createdAt = datetime()
        RETURN count(g) AS count
        """
        result = self.execute_write(cypher, {"groups": list(VALID_POI_GROUPS)})
        count = result[0]["count"] if result else 0
        logger.info(f"Ensured {count} POIGroup nodes exist")
        return count

    def _load_single_file(self, file_path: Path) -> Dict[str, Any]:
        """Load a single sub-attraction JSON file.

        Args:
            file_path: Path to the JSON file.

        Returns:
            Statistics for this file.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        location = data.get("location", file_path.stem)
        pois = data.get("pois", [])

        logger.info(f"Processing {len(pois)} POIs for location '{location}'")

        created_count = 0
        relationship_count = 0

        for poi in pois:
            try:
                result = self._create_sub_attraction(poi, location)
                if result.get("created"):
                    created_count += 1
                relationship_count += result.get("relationships", 0)
            except Exception as e:
                logger.warning(
                    f"Failed to import POI '{poi.get('name', 'unknown')}' "
                    f"for {location}: {e}"
                )

        logger.info(
            f"Location '{location}': created {created_count} sub-attractions, "
            f"{relationship_count} relationships"
        )

        return {
            "sub_attractions_created": created_count,
            "relationships_created": relationship_count,
        }

    def _create_sub_attraction(
        self, poi: Dict[str, Any], parent_location: str
    ) -> Dict[str, Any]:
        """Create a single SubAttraction node with all its relationships.

        Args:
            poi: POI data dictionary from JSON.
            parent_location: Name of the parent attraction/location.

        Returns:
            Dictionary with creation status and relationship count.
        """
        google = poi.get("google_enrichment", {}) or {}
        tags = poi.get("tags", {})
        enriched = poi.get("enriched_data", {}) or {}
        address_info = google.get("address_info", {}) or {}
        admin_areas = address_info.get("administrative_areas", {}) or {}
        google_links = google.get("google_links", {}) or {}
        opening_hours = google.get("opening_hours", {}) or {}

        # Determine specific type from OSM tags
        amenity_type = tags.get("amenity", "")
        shop_type = tags.get("shop", "")
        tourism_type = tags.get("tourism", "")
        natural_type = tags.get("natural", "")
        historic_type = tags.get("historic", "")

        # Build a composite type string for the primary category
        primary_type = (
            amenity_type or shop_type or tourism_type or natural_type or historic_type or ""
        )

        # Extract religion/denomination if present
        religion_data = enriched.get("religion", {}) or {}
        food_data = enriched.get("food", {}) or {}
        business_data = enriched.get("business", {}) or {}

        # Extract opening hours weekday text for storage
        weekday_text = opening_hours.get("weekday_text", [])

        # Extract reviews as JSON string
        reviews = google.get("reviews", [])

        place_id = google.get("place_id", "")
        # Use place_id as unique key; if missing, use name+parent as fallback
        unique_key = place_id if place_id else f"{poi.get('name', '')}_{parent_location}"

        cypher = """
        MERGE (s:SubAttraction {googlePlaceId: $googlePlaceId})
        SET s.name = $name,
            s.parentLocation = $parentLocation,
            s.latitude = $latitude,
            s.longitude = $longitude,

            // OSM classification
            s.amenityType = $amenityType,
            s.shopType = $shopType,
            s.tourismType = $tourismType,
            s.naturalType = $naturalType,
            s.historicType = $historicType,
            s.primaryType = $primaryType,
            s.osmTags = $osmTags,
            s.groups = $groups,

            // Religion / cultural
            s.religion = $religion,
            s.denomination = $denomination,

            // Food / dining
            s.cuisine = $cuisine,

            // Business / brand
            s.brand = $brand,

            // Google Places data
            s.rating = $rating,
            s.userRatingsTotal = $userRatingsTotal,
            s.priceLevel = $priceLevel,
            s.website = $website,
            s.phone = $phone,
            s.internationalPhone = $internationalPhone,
            s.formattedAddress = $formattedAddress,
            s.businessStatus = $businessStatus,
            s.editorialSummary = $editorialSummary,
            s.vicinity = $vicinity,
            s.placeTypes = $placeTypes,
            s.plusCode = $plusCode,

            // Address components
            s.country = $country,
            s.province = $province,
            s.district = $district,
            s.city = $city,
            s.postalCode = $postalCode,

            // Links
            s.googleMapsUrl = $googleMapsUrl,
            s.googleMapsDirectionsUrl = $googleMapsDirectionsUrl,
            s.googleEarthUrl = $googleEarthUrl,
            s.googleStreetViewUrl = $googleStreetViewUrl,

            // Opening hours (as JSON)
            s.openingHours = $openingHours,
            s.weekdayText = $weekdayText,

            // Photos & reviews (as JSON strings)
            s.photos = $photos,
            s.reviews = $reviews,

            // Metadata
            s.enrichedAt = $enrichedAt,
            s.updatedAt = datetime()
        WITH s
        WHERE s.createdAt IS NULL
        SET s.createdAt = datetime()
        RETURN s.name AS name, s.googlePlaceId AS placeId
        """

        params = {
            "googlePlaceId": unique_key,
            "name": poi.get("name", ""),
            "parentLocation": parent_location,
            "latitude": poi.get("lat"),
            "longitude": poi.get("lon"),
            # OSM classification
            "amenityType": amenity_type,
            "shopType": shop_type,
            "tourismType": tourism_type,
            "naturalType": natural_type,
            "historicType": historic_type,
            "primaryType": primary_type,
            "osmTags": json.dumps(tags),
            "groups": json.dumps(poi.get("groups", [])),
            # Religion
            "religion": religion_data.get("religion", tags.get("religion", "")),
            "denomination": religion_data.get("denomination", tags.get("denomination", "")),
            # Food
            "cuisine": food_data.get("cuisine", tags.get("cuisine", "")),
            # Business
            "brand": business_data.get("brand", tags.get("brand", "")),
            # Google Places
            "rating": google.get("rating"),
            "userRatingsTotal": google.get("user_ratings_total"),
            "priceLevel": google.get("price_level"),
            "website": google.get("website", ""),
            "phone": google.get("phone", ""),
            "internationalPhone": google.get("international_phone", ""),
            "formattedAddress": google.get("formatted_address", ""),
            "businessStatus": google.get("business_status", ""),
            "editorialSummary": google.get("editorial_summary", ""),
            "vicinity": google.get("vicinity", ""),
            "placeTypes": json.dumps(google.get("place_types", [])),
            "plusCode": google.get("plus_code", ""),
            # Address
            "country": admin_areas.get("country", "Sri Lanka"),
            "province": admin_areas.get("province", ""),
            "district": admin_areas.get("district", ""),
            "city": admin_areas.get("city", ""),
            "postalCode": admin_areas.get("postal_code", ""),
            # Links
            "googleMapsUrl": google.get("google_maps_url", ""),
            "googleMapsDirectionsUrl": google_links.get("google_maps_directions", ""),
            "googleEarthUrl": google_links.get("google_earth", ""),
            "googleStreetViewUrl": google_links.get("google_street_view", ""),
            # Opening hours
            "openingHours": json.dumps(opening_hours) if opening_hours else "{}",
            "weekdayText": json.dumps(weekday_text),
            # Photos & reviews
            "photos": json.dumps(google.get("photos", [])),
            "reviews": json.dumps(reviews),
            # Metadata
            "enrichedAt": google.get("enriched_at", ""),
        }

        result = self.execute_write(cypher, params)
        created = bool(result)

        # Create relationships
        rel_count = 0

        # 1) SUB_ATTRACTION_OF -> Attraction (parent)
        rel_count += self._link_to_parent_attraction(unique_key, parent_location)

        # 2) LOCATED_IN -> District
        district = admin_areas.get("district", "")
        if district:
            rel_count += self._link_to_district(unique_key, district)

        # 3) IN_PROVINCE -> Province
        province = admin_areas.get("province", "")
        if province:
            rel_count += self._link_to_province(unique_key, province)

        # 4) BELONGS_TO_GROUP -> POIGroup
        for group in poi.get("groups", []):
            if group in VALID_POI_GROUPS:
                rel_count += self._link_to_group(unique_key, group)

        return {"created": created, "relationships": rel_count}

    # ------------------------------------------------------------------
    # Relationship Helpers
    # ------------------------------------------------------------------

    def _link_to_parent_attraction(self, place_id: str, parent_location: str) -> int:
        """Create SUB_ATTRACTION_OF relationship to parent Attraction.

        Uses case-insensitive matching on the attraction title.
        """
        cypher = """
        MATCH (s:SubAttraction {googlePlaceId: $placeId})
        MATCH (a:Attraction)
        WHERE toLower(a.title) = toLower($parentLocation)
           OR toLower(a.city) = toLower($parentLocation)
        WITH s, a LIMIT 1
        MERGE (s)-[:SUB_ATTRACTION_OF]->(a)
        RETURN count(*) AS count
        """
        result = self.execute_write(
            cypher, {"placeId": place_id, "parentLocation": parent_location}
        )
        return result[0]["count"] if result else 0

    def _link_to_district(self, place_id: str, district_name: str) -> int:
        """Create LOCATED_IN relationship to District."""
        cypher = """
        MATCH (s:SubAttraction {googlePlaceId: $placeId})
        MATCH (d:District {name: $district})
        MERGE (s)-[:LOCATED_IN]->(d)
        RETURN count(*) AS count
        """
        result = self.execute_write(
            cypher, {"placeId": place_id, "district": district_name}
        )
        return result[0]["count"] if result else 0

    def _link_to_province(self, place_id: str, province_name: str) -> int:
        """Create IN_PROVINCE relationship to Province."""
        cypher = """
        MATCH (s:SubAttraction {googlePlaceId: $placeId})
        MATCH (p:Province {name: $province})
        MERGE (s)-[:IN_PROVINCE]->(p)
        RETURN count(*) AS count
        """
        result = self.execute_write(
            cypher, {"placeId": place_id, "province": province_name}
        )
        return result[0]["count"] if result else 0

    def _link_to_group(self, place_id: str, group_name: str) -> int:
        """Create BELONGS_TO_GROUP relationship to POIGroup."""
        cypher = """
        MATCH (s:SubAttraction {googlePlaceId: $placeId})
        MATCH (g:POIGroup {name: $group})
        MERGE (s)-[:BELONGS_TO_GROUP]->(g)
        RETURN count(*) AS count
        """
        result = self.execute_write(
            cypher, {"placeId": place_id, "group": group_name}
        )
        return result[0]["count"] if result else 0

    def _create_hotel_links(self) -> int:
        """Create NEAR_HOTEL relationships between SubAttractions and Hotels.

        Links are created when:
        1. A Hotel's nearby_places share the same Google Place ID as a SubAttraction
        2. A Hotel and SubAttraction are in the same district and within ~5km
        """
        # Strategy 1: Match by proximity (same parent attraction location)
        cypher = """
        MATCH (s:SubAttraction)-[:SUB_ATTRACTION_OF]->(a:Attraction)
        MATCH (h:Hotel)-[:NEAR_ATTRACTION]->(a)
        WHERE s.latitude IS NOT NULL AND s.longitude IS NOT NULL
          AND h.latitude IS NOT NULL AND h.longitude IS NOT NULL
          AND point.distance(
              point({latitude: s.latitude, longitude: s.longitude}),
              point({latitude: h.latitude, longitude: h.longitude})
          ) < 5000
        MERGE (s)-[r:NEAR_HOTEL]->(h)
        SET r.distance_meters = point.distance(
            point({latitude: s.latitude, longitude: s.longitude}),
            point({latitude: h.latitude, longitude: h.longitude})
        )
        RETURN count(r) AS count
        """
        try:
            result = self.execute_write(cypher)
            count = result[0]["count"] if result else 0
            logger.info(f"Created {count} NEAR_HOTEL relationships via proximity")
            return count
        except Exception as e:
            logger.warning(f"Hotel proximity linking failed (may not have Hotel nodes): {e}")
            return 0

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> Dict[str, Any]:
        """Remove all SubAttraction nodes and related relationships."""
        try:
            logger.info("Cleaning up sub-attraction data...")

            # Count before
            before = self.execute_query(
                "MATCH (s:SubAttraction) RETURN count(s) AS count"
            )
            before_count = before[0]["count"] if before else 0

            # Delete SubAttraction nodes and their relationships
            self.execute_write("MATCH (s:SubAttraction) DETACH DELETE s")

            # Delete orphaned POIGroup nodes (no remaining relationships)
            self.execute_write(
                """
                MATCH (g:POIGroup)
                WHERE NOT (g)<-[:BELONGS_TO_GROUP]-()
                DELETE g
                """
            )

            logger.info(f"Cleaned up {before_count} SubAttraction nodes")

            return {
                "success": True,
                "message": f"Removed {before_count} sub-attraction nodes",
                "deleted_count": before_count,
            }

        except Exception as e:
            logger.error(f"Failed to cleanup sub-attractions: {e}")
            raise

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def query(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query sub-attractions with dynamic filters.

        Supported filters:
            parent_attraction, group, district, province, name,
            amenity_type, min_rating, has_opening_hours, limit
        """
        logger.info(f"Querying sub-attractions with filters: {filters}")

        match_clause = "MATCH (s:SubAttraction)"
        where_clauses: List[str] = []
        params: Dict[str, Any] = {}

        # Parent attraction filter
        if filters.get("parent_attraction"):
            match_clause = (
                "MATCH (s:SubAttraction)-[:SUB_ATTRACTION_OF]->(a:Attraction)"
            )
            where_clauses.append("toLower(a.title) = toLower($parentAttraction)")
            params["parentAttraction"] = filters["parent_attraction"]

        # Group filter
        if filters.get("group"):
            if "SUB_ATTRACTION_OF" in match_clause:
                match_clause += "\nMATCH (s)-[:BELONGS_TO_GROUP]->(g:POIGroup)"
            else:
                match_clause = (
                    "MATCH (s:SubAttraction)-[:BELONGS_TO_GROUP]->(g:POIGroup)"
                )
            where_clauses.append("toLower(g.name) = toLower($group)")
            params["group"] = filters["group"]

        # District filter
        if filters.get("district"):
            where_clauses.append("toLower(s.district) = toLower($district)")
            params["district"] = filters["district"]

        # Province filter
        if filters.get("province"):
            where_clauses.append("toLower(s.province) = toLower($province)")
            params["province"] = filters["province"]

        # Name search (partial match)
        if filters.get("name"):
            where_clauses.append("toLower(s.name) CONTAINS toLower($name)")
            params["name"] = filters["name"]

        # Amenity type filter
        if filters.get("amenity_type"):
            where_clauses.append(
                "(toLower(s.amenityType) = toLower($amenityType) "
                "OR toLower(s.shopType) = toLower($amenityType) "
                "OR toLower(s.tourismType) = toLower($amenityType) "
                "OR toLower(s.primaryType) = toLower($amenityType))"
            )
            params["amenityType"] = filters["amenity_type"]

        # Minimum rating
        if filters.get("min_rating") is not None:
            where_clauses.append("s.rating >= $minRating")
            params["minRating"] = filters["min_rating"]

        # Has opening hours
        if filters.get("has_opening_hours") is not None:
            if filters["has_opening_hours"]:
                where_clauses.append("s.openingHours IS NOT NULL AND s.openingHours <> '{}'")
            else:
                where_clauses.append("(s.openingHours IS NULL OR s.openingHours = '{}')")

        where_clause = ""
        if where_clauses:
            where_clause = " WHERE " + " AND ".join(where_clauses)

        limit = filters.get("limit", 20)

        full_query = f"""
        {match_clause}
        {where_clause}
        OPTIONAL MATCH (s)-[:SUB_ATTRACTION_OF]->(parent:Attraction)
        OPTIONAL MATCH (s)-[:LOCATED_IN]->(dist:District)
        OPTIONAL MATCH (dist)-[:IN_PROVINCE]->(prov:Province)
        OPTIONAL MATCH (s)-[:BELONGS_TO_GROUP]->(grp:POIGroup)
        RETURN s.name AS name,
               s.googlePlaceId AS googlePlaceId,
               s.parentLocation AS parentLocation,
               parent.title AS parentAttraction,
               s.latitude AS latitude,
               s.longitude AS longitude,
               s.amenityType AS amenityType,
               s.shopType AS shopType,
               s.tourismType AS tourismType,
               s.primaryType AS primaryType,
               s.rating AS rating,
               s.userRatingsTotal AS userRatingsTotal,
               s.formattedAddress AS formattedAddress,
               s.website AS website,
               s.phone AS phone,
               s.businessStatus AS businessStatus,
               s.editorialSummary AS editorialSummary,
               s.googleMapsUrl AS googleMapsUrl,
               s.weekdayText AS weekdayText,
               s.photos AS photos,
               s.religion AS religion,
               s.cuisine AS cuisine,
               s.brand AS brand,
               s.groups AS groups,
               s.priceLevel AS priceLevel,
               s.vicinity AS vicinity,
               dist.name AS districtNode,
               prov.name AS provinceNode,
               collect(DISTINCT grp.name) AS poiGroups
        ORDER BY s.rating DESC, s.name
        LIMIT {limit}
        """

        result = self.execute_query(full_query, params)
        logger.info(f"Found {len(result)} sub-attractions")
        return result

    def get_by_parent(self, parent_attraction: str) -> List[Dict[str, Any]]:
        """Get all sub-attractions for a parent attraction.

        Args:
            parent_attraction: Title of the parent attraction.
        """
        logger.info(f"Getting sub-attractions for: {parent_attraction}")

        cypher = """
        MATCH (s:SubAttraction)-[:SUB_ATTRACTION_OF]->(a:Attraction)
        WHERE toLower(a.title) = toLower($parent)
        OPTIONAL MATCH (s)-[:BELONGS_TO_GROUP]->(g:POIGroup)
        OPTIONAL MATCH (s)-[:LOCATED_IN]->(d:District)
        RETURN s.name AS name,
               s.googlePlaceId AS googlePlaceId,
               s.parentLocation AS parentLocation,
               a.title AS parentAttraction,
               s.latitude AS latitude,
               s.longitude AS longitude,
               s.primaryType AS primaryType,
               s.amenityType AS amenityType,
               s.rating AS rating,
               s.userRatingsTotal AS userRatingsTotal,
               s.formattedAddress AS formattedAddress,
               s.website AS website,
               s.phone AS phone,
               s.businessStatus AS businessStatus,
               s.editorialSummary AS editorialSummary,
               s.googleMapsUrl AS googleMapsUrl,
               s.weekdayText AS weekdayText,
               s.photos AS photos,
               s.religion AS religion,
               s.cuisine AS cuisine,
               s.brand AS brand,
               s.groups AS groups,
               s.priceLevel AS priceLevel,
               d.name AS district,
               collect(DISTINCT g.name) AS poiGroups
        ORDER BY s.rating DESC, s.name
        """

        return self.execute_query(cypher, {"parent": parent_attraction})

    def get_by_group(self, group_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get all sub-attractions belonging to a specific POI group.

        Args:
            group_name: POI group name (e.g., 'Religious / Spiritual').
            limit: Maximum results.
        """
        logger.info(f"Getting sub-attractions for group: {group_name}")

        cypher = """
        MATCH (s:SubAttraction)-[:BELONGS_TO_GROUP]->(g:POIGroup {name: $group})
        OPTIONAL MATCH (s)-[:SUB_ATTRACTION_OF]->(a:Attraction)
        OPTIONAL MATCH (s)-[:LOCATED_IN]->(d:District)
        RETURN s.name AS name,
               s.googlePlaceId AS googlePlaceId,
               s.parentLocation AS parentLocation,
               a.title AS parentAttraction,
               s.latitude AS latitude,
               s.longitude AS longitude,
               s.primaryType AS primaryType,
               s.rating AS rating,
               s.userRatingsTotal AS userRatingsTotal,
               s.formattedAddress AS formattedAddress,
               s.website AS website,
               s.phone AS phone,
               s.businessStatus AS businessStatus,
               s.googleMapsUrl AS googleMapsUrl,
               s.weekdayText AS weekdayText,
               s.religion AS religion,
               s.cuisine AS cuisine,
               d.name AS district,
               g.name AS poiGroup
        ORDER BY s.rating DESC, s.name
        LIMIT $limit
        """

        return self.execute_query(cypher, {"group": group_name, "limit": limit})

    def get_nearby_hotels(self, place_id: str) -> List[Dict[str, Any]]:
        """Get hotels near a specific sub-attraction.

        Args:
            place_id: Google Place ID of the sub-attraction.
        """
        cypher = """
        MATCH (s:SubAttraction {googlePlaceId: $placeId})-[r:NEAR_HOTEL]->(h:Hotel)
        RETURN h.name AS hotelName,
               h.rating AS hotelRating,
               h.rate_per_night AS ratePerNight,
               h.city AS city,
               r.distance_meters AS distanceMeters
        ORDER BY r.distance_meters
        """
        return self.execute_query(cypher, {"placeId": place_id})

    def get_groups(self) -> List[Dict[str, Any]]:
        """Get all POI groups with sub-attraction counts."""
        cypher = """
        MATCH (g:POIGroup)
        OPTIONAL MATCH (g)<-[:BELONGS_TO_GROUP]-(s:SubAttraction)
        RETURN g.name AS group,
               count(s) AS subAttractionCount
        ORDER BY subAttractionCount DESC
        """
        return self.execute_query(cypher)

    def get_unique_group_tags(self) -> List[str]:
        """Get all unique group tags from SubAttraction nodes.

        Unwinds the ``groups`` list property stored on every SubAttraction
        and returns a deduplicated, sorted list of tag strings.
        """
        cypher = """
        MATCH (s:SubAttraction)
        WHERE s.groups IS NOT NULL
        UNWIND s.groups AS tag
        WITH DISTINCT tag
        WHERE tag IS NOT NULL AND trim(tag) <> ''
        RETURN tag
        ORDER BY tag
        """
        rows = self.execute_query(cypher)
        return [row["tag"] for row in rows]

    def get_unique_osm_tag_keys(self) -> List[str]:
        """Get all unique OSM tag keys stored across every SubAttraction node.

        ``osmTags`` is persisted as a JSON string (e.g.
        ``'{"amenity": "restaurant", "name": "..."}``).  APOC is used to
        parse each string into a map so we can enumerate its keys.
        Returns a deduplicated, sorted list.
        """
        cypher = """
        MATCH (s:SubAttraction)
        WHERE s.osmTags IS NOT NULL AND s.osmTags <> '{}' AND s.osmTags <> ''
        WITH apoc.convert.fromJsonMap(s.osmTags) AS tagsMap
        UNWIND keys(tagsMap) AS tagKey
        WITH DISTINCT tagKey
        WHERE tagKey IS NOT NULL AND trim(tagKey) <> ''
        RETURN tagKey
        ORDER BY tagKey
        """
        rows = self.execute_query(cypher)
        return [row["tagKey"] for row in rows]

    def get_osm_tags_with_values(self) -> Dict[str, List[str]]:
        """Get all unique OSM tag keys and their unique values across all SubAttraction nodes.

        Returns a dict mapping each tag key to a sorted list of distinct
        non-empty values found for that key.
        """
        cypher = """
        MATCH (s:SubAttraction)
        WHERE s.osmTags IS NOT NULL AND s.osmTags <> '{}' AND s.osmTags <> ''
        WITH apoc.convert.fromJsonMap(s.osmTags) AS tagsMap
        UNWIND keys(tagsMap) AS tagKey
        WITH tagKey, tagsMap[tagKey] AS tagValue
        WHERE tagKey IS NOT NULL AND trim(tagKey) <> ''
          AND tagValue IS NOT NULL AND trim(toString(tagValue)) <> ''
        WITH tagKey, trim(toString(tagValue)) AS cleanValue
        WITH tagKey, collect(DISTINCT cleanValue) AS values
        RETURN tagKey, apoc.coll.sort(values) AS values
        ORDER BY tagKey
        """
        rows = self.execute_query(cypher)
        return {row["tagKey"]: row["values"] for row in rows}

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about sub-attraction data."""
        cypher = """
        MATCH (s:SubAttraction)
        OPTIONAL MATCH (s)-[:SUB_ATTRACTION_OF]->(a:Attraction)
        OPTIONAL MATCH (s)-[:BELONGS_TO_GROUP]->(g:POIGroup)
        OPTIONAL MATCH (s)-[:LOCATED_IN]->(d:District)
        OPTIONAL MATCH (s)-[h:NEAR_HOTEL]->()
        WITH s, a, g, d, h
        RETURN count(DISTINCT s) AS totalSubAttractions,
               count(DISTINCT a) AS totalParentAttractions,
               count(DISTINCT g) AS totalGroups,
               count(DISTINCT d) AS totalDistricts,
               count(DISTINCT h) AS totalHotelLinks,
               count(CASE WHEN s.rating IS NOT NULL THEN 1 END) AS withRating,
               count(CASE WHEN s.website IS NOT NULL AND s.website <> '' THEN 1 END) AS withWebsite,
               count(CASE WHEN s.openingHours IS NOT NULL AND s.openingHours <> '{}' THEN 1 END) AS withOpeningHours,
               avg(s.rating) AS averageRating
        """
        result = self.execute_query(cypher)
        if not result:
            return {}

        stats = result[0]

        # Get group breakdown
        group_query = """
        MATCH (g:POIGroup)<-[:BELONGS_TO_GROUP]-(s:SubAttraction)
        RETURN g.name AS group, count(s) AS count
        ORDER BY count DESC
        """
        group_stats = self.execute_query(group_query)

        # Get parent breakdown
        parent_query = """
        MATCH (s:SubAttraction)-[:SUB_ATTRACTION_OF]->(a:Attraction)
        RETURN a.title AS parent, count(s) AS count
        ORDER BY count DESC
        """
        parent_stats = self.execute_query(parent_query)

        stats["byGroup"] = {r["group"]: r["count"] for r in group_stats}
        stats["byParent"] = {r["parent"]: r["count"] for r in parent_stats}

        return stats
