"""
Recommender — Route-based attraction discovery service.

Given a list of sampled route waypoints, queries Neo4j for SubAttraction
nodes whose coordinates fall within *corridor_km* of any waypoint (using
the Haversine-based ``point.distance`` function built into Neo4j).

Results are de-duplicated (a POI near two waypoints appears only once,
tagged with the nearest waypoint index and minimum distance).
"""

import json
import logging
import time
from typing import List, Dict, Any

from neo4j import Driver

from models.domain.recommender import (
    AttractionsOnRouteRequest,
    AttractionsOnRouteResponse,
    RouteSubAttractionItem,
    RoutePointResult,
)

logger = logging.getLogger(__name__)


class RouteAttractionService:
    """Find sub-attractions along a series of route waypoints."""

    def __init__(self, driver: Driver):
        self.driver = driver

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_attractions_on_route(
        self, request: AttractionsOnRouteRequest
    ) -> AttractionsOnRouteResponse:
        """Return sub-attractions within *corridor_km* of the sampled route,
        grouped by each route waypoint."""
        start = time.time()

        corridor_m = request.corridor_km * 1000  # Neo4j point.distance → metres

        # Track which POIs have already been assigned so each appears only once
        # (assigned to the first/closest waypoint that discovers it).
        globally_seen: set[str] = set()
        total_matched = 0

        route_point_results: List[RoutePointResult] = []

        with self.driver.session() as session:
            for idx, point in enumerate(request.sampled_route_points):
                lat, lon = point[0], point[1]
                records = self._query_nearby(session, lat, lon, corridor_m, request.limit)

                point_items: List[RouteSubAttractionItem] = []
                for rec in records:
                    key = rec.get("googlePlaceId") or rec.get("name", "")
                    if key in globally_seen:
                        continue  # already assigned to an earlier waypoint
                    globally_seen.add(key)

                    dist_m = rec.get("distance_m", 0.0)
                    point_items.append(self._record_to_item(rec, dist_m))

                total_matched += len(point_items)

                route_point_results.append(
                    RoutePointResult(
                        route_point=[lat, lon],
                        route_point_index=idx,
                        sub_attractions=point_items,
                        count=len(point_items),
                    )
                )

        elapsed_ms = round((time.time() - start) * 1000, 2)

        return AttractionsOnRouteResponse(
            status="ok",
            items=route_point_results,
            debug={
                "matched_count": total_matched,
                "corridor_km": request.corridor_km,
                "route_points_received": len(request.sampled_route_points),
                "query_ms": elapsed_ms,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _query_nearby(
        session, lat: float, lon: float, radius_m: float, limit: int
    ) -> List[Dict[str, Any]]:
        """Run a spatial proximity query for one waypoint."""
        cypher = """
        MATCH (s:SubAttraction)
        WHERE s.latitude IS NOT NULL AND s.longitude IS NOT NULL
        WITH s,
             point.distance(
                 point({latitude: s.latitude, longitude: s.longitude}),
                 point({latitude: $lat, longitude: $lon})
             ) AS dist
        WHERE dist <= $radius
        OPTIONAL MATCH (s)-[:SUB_ATTRACTION_OF]->(a:Attraction)
        OPTIONAL MATCH (s)-[:LOCATED_IN]->(d:District)
        OPTIONAL MATCH (d)-[:IN_PROVINCE]->(p:Province)
        OPTIONAL MATCH (s)-[:BELONGS_TO_GROUP]->(g:POIGroup)
        RETURN s.name             AS name,
               s.googlePlaceId    AS googlePlaceId,
               s.parentLocation   AS parentLocation,
               s.latitude         AS latitude,
               s.longitude        AS longitude,
               s.primaryType      AS primaryType,
               s.amenityType      AS amenityType,
               s.shopType         AS shopType,
               s.tourismType      AS tourismType,
               s.groups           AS groups,
               s.rating           AS rating,
               s.userRatingsTotal AS userRatingsTotal,
               s.formattedAddress AS formattedAddress,
               s.city             AS city,
               s.district         AS district,
               s.province         AS province,
               s.editorialSummary AS editorialSummary,
               s.website          AS website,
               s.phone            AS phone,
               s.googleMapsUrl    AS googleMapsUrl,
               s.weekdayText      AS weekdayText,
               s.photos           AS photos,
               s.businessStatus   AS businessStatus,
               s.cuisine          AS cuisine,
               s.religion         AS religion,
               dist               AS distance_m,
               d.name             AS districtNode,
               p.name             AS provinceNode,
               collect(DISTINCT g.name) AS poiGroups
        ORDER BY dist ASC
        LIMIT $limit
        """
        result = session.run(cypher, lat=lat, lon=lon, radius=radius_m, limit=limit)
        return [dict(r) for r in result]

    @staticmethod
    def _parse_json_field(value: Any) -> Any:
        """Safely parse a JSON-encoded string field, returning original on failure."""
        if value is None:
            return None
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return value
        return value

    def _record_to_item(
        self, rec: Dict[str, Any], distance_m: float
    ) -> RouteSubAttractionItem:
        """Convert a Neo4j record dict into a response item."""
        # Determine category from available type fields
        category = (
            rec.get("primaryType")
            or rec.get("amenityType")
            or rec.get("shopType")
            or rec.get("tourismType")
            or None
        )

        # Parse groups — stored as JSON string or list
        raw_groups = self._parse_json_field(rec.get("groups"))
        poi_groups = rec.get("poiGroups") or []
        if isinstance(raw_groups, list):
            # merge stored groups with relationship-based groups, deduplicate
            all_groups = list(dict.fromkeys(raw_groups + poi_groups))
        else:
            all_groups = poi_groups or None

        # Parse photos & weekday text
        photos = self._parse_json_field(rec.get("photos"))
        if isinstance(photos, list):
            photos = [p for p in photos if isinstance(p, str)] or None
        else:
            photos = None

        weekday = self._parse_json_field(rec.get("weekdayText"))
        if isinstance(weekday, list):
            opening_hours = [str(w) for w in weekday] or None
        else:
            opening_hours = None

        return RouteSubAttractionItem(
            name=rec.get("name", ""),
            latitude=rec.get("latitude"),
            longitude=rec.get("longitude"),
            parent_location=rec.get("parentLocation"),
            category=category,
            groups=all_groups if all_groups else None,
            rating=rec.get("rating"),
            user_ratings_total=rec.get("userRatingsTotal"),
            formatted_address=rec.get("formattedAddress"),
            city=rec.get("city") or rec.get("districtNode"),
            district=rec.get("district") or rec.get("districtNode"),
            province=rec.get("province") or rec.get("provinceNode"),
            editorial_summary=rec.get("editorialSummary"),
            website=rec.get("website"),
            phone=rec.get("phone"),
            google_maps_url=rec.get("googleMapsUrl"),
            opening_hours=opening_hours,
            photos=photos,
            business_status=rec.get("businessStatus"),
            cuisine=rec.get("cuisine"),
            religion=rec.get("religion"),
            distance_km=round(distance_m / 1000, 3) if distance_m else None,
        )
