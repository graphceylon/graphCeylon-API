"""
Orchestrator Hotel Service

Business logic for hotel search functionality used by orchestrator service.
"""

import time
from typing import List, Dict, Any

from neo4j import Driver

from core.utils import normalize_location_name, CITY_ALIASES
from models.domain.hotel import (
    AccommodationSearchRequest,
    HotelItemResponse,
    OrchestratorSearchResponse,
)


class OrchestratorHotelService:
    """Service for handling orchestrator hotel search requests."""

    # Currency conversion rate (approximate)
    USD_TO_LKR_RATE = 300.0

    def __init__(self, driver: Driver):
        self.driver = driver

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_hotels(self, request: AccommodationSearchRequest) -> OrchestratorSearchResponse:
        """Search hotels based on orchestrator request criteria.

        Filters by city/country, star rating range, required amenities, and budget.
        City matching checks hotel city, district, province, and linked attraction name
        (case-insensitive), mirroring the sub-attraction city filter pattern.
        """
        start_time = time.time()

        # Normalise city (handles aliases like "colombo" -> "Colombo")
        if request.city:
            request = request.copy(update={"city": normalize_location_name(request.city, CITY_ALIASES)})

        try:
            with self.driver.session() as session:
                cypher_query, params = self._build_query(request)
                result = session.run(cypher_query, **params)
                records = list(result)

                items = self._transform_records_to_items(records)
                query_time_ms = round((time.time() - start_time) * 1000, 2)
                trace = self._build_trace(request, query_time_ms, len(items))

                return OrchestratorSearchResponse(
                    ok=True,
                    count=len(items),
                    items=items,
                    trace=trace,
                )

        except Exception as e:
            return OrchestratorSearchResponse(
                ok=False,
                error="Neo4j query failed",
                details=str(e),
            )

    # ------------------------------------------------------------------
    # Query building
    # ------------------------------------------------------------------

    def _build_query(self, request: AccommodationSearchRequest) -> tuple[str, Dict[str, Any]]:
        """Build Cypher query and parameters from *request*."""
        params: Dict[str, Any] = {"limit": request.limit}

        # Start with MATCH + OPTIONAL MATCHes, then move into a WITH block
        # so that WHERE filters act as hard row-level filters — not as
        # constraints on an OPTIONAL MATCH (which would only nullify the
        # optional variables instead of excluding the row).
        cypher_query = """MATCH (h:Hotel)
        OPTIONAL MATCH (h)-[:LOCATED_IN_DISTRICT]->(d:District)
        OPTIONAL MATCH (h)-[:LOCATED_IN_PROVINCE]->(p:Province)
        WITH h, d, p
        """

        where_clauses: list[str] = []

        if request.city:
            # Match on the hotel's own city field first (exact match).
            # Fall back to exact district / province name only when the
            # hotel has no explicit city.  We use equality (not CONTAINS)
            # to avoid false positives such as "Kegalle" matching "Galle".
            where_clauses.append(
                "("
                "toLower(h.city) = toLower($city) "
                "OR (h.city IS NULL AND toLower(h.district) = toLower($city)) "
                "OR (h.city IS NULL AND toLower(d.name) = toLower($city)) "
                "OR (h.city IS NULL AND toLower(p.name) = toLower($city))"
                ")"
            )
            params["city"] = request.city

        if request.country and request.country.lower() == "sri lanka":
            where_clauses.append("p IS NOT NULL")

        # Map hotel star tiers to Google review score thresholds:
        # 5-star → 4.5+,  4-star → 4.0+,  3-star → 3.5+,  2-star → 3.0+,  1-star → 0+
        STAR_TO_MIN_SCORE = {5: 4.5, 4: 4.0, 3: 3.5, 2: 3.0, 1: 0.0}
        STAR_TO_MAX_SCORE = {5: 5.0, 4: 4.49, 3: 3.99, 2: 3.49, 1: 2.99}

        if request.min_star_rating is not None:
            where_clauses.append("h.rating >= $min_rating")
            params["min_rating"] = STAR_TO_MIN_SCORE.get(request.min_star_rating, float(request.min_star_rating))

        if request.max_star_rating is not None:
            where_clauses.append("h.rating <= $max_rating")
            params["max_rating"] = STAR_TO_MAX_SCORE.get(request.max_star_rating, float(request.max_star_rating))

        if request.max_price_lkr is not None:
            max_price_usd = request.max_price_lkr / self.USD_TO_LKR_RATE
            where_clauses.append("h.rate_per_night <= $max_price")
            params["max_price"] = max_price_usd

        if where_clauses:
            cypher_query += "WHERE " + " AND ".join(where_clauses) + "\n"

        if request.must_have_amenities:
            cypher_query += """
            WITH h, d, p
            MATCH (h)-[:OFFERS_AMENITY]->(am:Amenity)
            WHERE toLower(am.name) IN $required_amenities
            WITH h, d, p, count(DISTINCT am) as amenity_match_count
            WHERE amenity_match_count = $required_amenity_count
            """
            params["required_amenities"] = [a.lower() for a in request.must_have_amenities]
            params["required_amenity_count"] = len(request.must_have_amenities)
        else:
            cypher_query += "WITH h, d, p\n"

        cypher_query += """
        OPTIONAL MATCH (h)-[:OFFERS_AMENITY]->(amenity:Amenity)

        WITH h, d, p, collect(DISTINCT toLower(amenity.name)) as amenities

        RETURN
            h.hotel_id as hotel_id,
            h.name as name,
            COALESCE(h.city, d.name) as city,
            'Sri Lanka' as country,
            h.rating as star_rating,
            h.rate_per_night as rate_usd,
            amenities,
            COALESCE(h.description, p.name + ', ' + d.name) as address,
            h.latitude as latitude,
            h.longitude as longitude,
            p.name as province,
            d.name as district
        ORDER BY h.rating DESC, h.rate_per_night ASC
        LIMIT $limit
        """

        return cypher_query, params

    # ------------------------------------------------------------------
    # Record transformation
    # ------------------------------------------------------------------

    def _transform_records_to_items(self, records: List) -> List[HotelItemResponse]:
        """Transform Neo4j records to ``HotelItemResponse`` objects."""
        items: list[HotelItemResponse] = []

        for record in records:
            rate_usd = record["rate_usd"] if record["rate_usd"] else 100.0
            base_price_lkr = rate_usd * self.USD_TO_LKR_RATE
            min_price = base_price_lkr * 0.9
            max_price = base_price_lkr * 1.1

            star_rating = None
            if record["star_rating"] is not None:
                star_rating = int(round(record["star_rating"]))

            address = self._build_address(
                record["district"],
                record["province"],
                record["address"],
            )

            geo = {
                "lat": record["latitude"] if record["latitude"] else 6.9271,
                "lon": record["longitude"] if record["longitude"] else 79.8612,
            }

            items.append(
                HotelItemResponse(
                    name=record["name"],
                    city=record["city"],
                    country="Sri Lanka",
                    star_rating=star_rating,
                    price_range_lkr={"min": round(min_price, 2), "max": round(max_price, 2)},
                    amenities=record["amenities"] or [],
                    address=address,
                    geo=geo,
                    source="neo4j",
                    kg_id=f"Hotel:{record['hotel_id']}",
                )
            )

        return items

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_address(district: str, province: str, fallback: str) -> str:
        """Build address string from district and province."""
        parts = [p for p in (district, province) if p]
        return ", ".join(parts) if parts else fallback

    def _build_trace(
        self,
        request: AccommodationSearchRequest,
        query_time_ms: float,
        result_count: int,
    ) -> Dict[str, Any]:
        """Build trace / debug information for the response."""
        trace: Dict[str, Any] = {"cypher_ms": query_time_ms, "filters_applied": {}}

        if request.city:
            trace["filters_applied"]["city"] = request.city
        if request.min_star_rating is not None:
            trace["filters_applied"]["min_star_rating"] = request.min_star_rating
        if request.max_star_rating is not None:
            trace["filters_applied"]["max_star_rating"] = request.max_star_rating
        if request.must_have_amenities:
            trace["filters_applied"]["must_have_amenities"] = request.must_have_amenities
        if request.max_price_lkr is not None:
            trace["filters_applied"]["max_price_lkr"] = request.max_price_lkr

        if request.trace:
            trace.update(request.trace)

        if result_count == 0:
            trace["reason"] = "No matches"

        return trace
