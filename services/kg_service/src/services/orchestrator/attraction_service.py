"""
Orchestrator Attraction Service

Business logic for attraction search functionality used by orchestrator service.
"""

import logging
from typing import List, Dict, Any, Optional

from neo4j import Driver

from core.utils import normalize_location_name, CITY_ALIASES
from models.domain.attraction import (
    AttractionSearchRequest,
    AttractionItem,
    AttractionSearchResponse,
)

logger = logging.getLogger(__name__)


class OrchestratorAttractionService:
    """Service for handling orchestrator attraction search requests."""

    def __init__(self, driver: Driver):
        self.driver = driver

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_attractions(self, request: AttractionSearchRequest) -> AttractionSearchResponse:
        """Search attractions using vector similarity or city-based lookup.
        
        Logic:
        1. If only city provided (no poi_category): Direct city-based search
        2. If both city and poi_category: Vector search filtered by city
        3. If only poi_category (no city): Vector search across all attractions
        """
        try:
            # Case 1: Only city provided (no poi_category or empty string)
            if not request.poi_category or request.poi_category.strip() == "":
                logger.info(f"Using city-based search for: {request.city}")
                city = normalize_location_name(request.city, CITY_ALIASES)
                attractions_data = self._get_attractions_by_city(
                    city=city,
                    country=request.country,
                    poi_name=request.poi_name,
                    limit=10,
                )
            # Case 2 & 3: poi_category provided
            else:
                # Case 2: Both city and poi_category provided
                if request.city and request.city.strip() != "":
                    logger.info(f"Using vector search for category '{request.poi_category}' in city '{request.city}'")
                    attractions_data = self._vector_search_by_category(
                        category=request.poi_category,
                        city=request.city,
                        country=request.country,
                        query=request.query or request.poi_category,
                        limit=10,
                    )
                # Case 3: Only poi_category, no city
                else:
                    logger.info(f"Using vector search for category '{request.poi_category}' across all cities")
                    attractions_data = self._vector_search_all_cities(
                        category=request.poi_category,
                        country=request.country,
                        query=request.query or request.poi_category,
                        limit=20,  # Return more results when searching all cities
                    )

            items = [self._map_to_item(data) for data in attractions_data]
            summary = self._generate_summary(items, request.city or "Sri Lanka", request.days)

            if not items:
                location_msg = f"in {request.city}" if request.city else "matching your criteria"
                return AttractionSearchResponse(
                    ok=False,
                    city=request.city or "",
                    country=request.country,
                    items=[],
                    summary="",
                    error="No attractions found",
                    details=f"No attractions available {location_msg}",
                )

            return AttractionSearchResponse(
                ok=True,
                city=request.city or "",
                country=request.country,
                items=items,
                summary=summary,
            )

        except Exception as e:
            logger.error(f"Attraction search failed: {e}", exc_info=True)
            return AttractionSearchResponse(
                ok=False,
                city=request.city or "",
                country=request.country,
                items=[],
                summary="",
                error="Attraction search failed",
                details=str(e),
            )

    # ------------------------------------------------------------------
    # Vector search
    # ------------------------------------------------------------------

    def _vector_search_by_category(
        self,
        category: str,
        city: str,
        country: str,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Use vector similarity search on description field, filtered by category and city."""
        try:
            from services.embeddings import embedding_service
            from core.config import settings

            logger.info(f"Vector search: category={category}, city={city}, query={query}")
            query_embedding = embedding_service.generate_embedding(query)

            if not query_embedding:
                logger.warning("Failed to generate embedding, falling back to regular search")
                return self._get_attractions_by_city(
                    city=normalize_location_name(city, CITY_ALIASES),
                    country=country,
                    poi_category=category,
                    limit=limit,
                )

            normalized_city = normalize_location_name(city, CITY_ALIASES)

            cypher = f"""
            CALL db.index.vector.queryNodes('{settings.vector_index_name}', $limit * 3, $embedding)
            YIELD node, score
            WHERE toLower(node.city) = toLower($city)
            RETURN node.title AS title,
                   node.description AS description,
                   node.imageUrl AS imageUrl,
                   node.latitude AS latitude,
                   node.longitude AS longitude,
                   node.formattedAddress AS formattedAddress,
                   node.city AS city,
                   node.district AS district,
                   node.province AS province,
                   node.rating AS rating,
                   node.userRatingsTotal AS userRatingsTotal,
                   node.website AS website,
                   node.phoneNumber AS phoneNumber,
                   node.placeTypes AS placeTypes,
                   node.googleMapsUrl AS googleMapsUrl,
                   node.editorialSummary AS editorialSummary,
                   node.vicinity AS vicinity,
                   score
            ORDER BY score DESC
            LIMIT $limit
            """

            with self.driver.session() as session:
                result = session.run(cypher, {
                    "embedding": query_embedding,
                    "city": normalized_city,
                    "limit": limit,
                })
                matches = [dict(record) for record in result]

            logger.info(f"Vector search found {len(matches)} results for city '{city}'")
            return matches

        except Exception as e:
            logger.error(f"Vector search failed: {e}, falling back to regular search")
            return self._get_attractions_by_city(
                city=normalize_location_name(city, CITY_ALIASES),
                country=country,
                poi_category=category,
                limit=limit,
            )

    def _vector_search_all_cities(
        self,
        category: str,
        country: str,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Use vector similarity search across all cities (no city filter)."""
        try:
            from services.embeddings import embedding_service
            from core.config import settings

            logger.info(f"Vector search (all cities): category={category}, query={query}")
            query_embedding = embedding_service.generate_embedding(query)

            if not query_embedding:
                logger.warning("Failed to generate embedding")
                return []

            cypher = f"""
            CALL db.index.vector.queryNodes('{settings.vector_index_name}', $limit * 2, $embedding)
            YIELD node, score
            RETURN node.title AS title,
                   node.description AS description,
                   node.imageUrl AS imageUrl,
                   node.latitude AS latitude,
                   node.longitude AS longitude,
                   node.formattedAddress AS formattedAddress,
                   node.city AS city,
                   node.district AS district,
                   node.province AS province,
                   node.rating AS rating,
                   node.userRatingsTotal AS userRatingsTotal,
                   node.website AS website,
                   node.phoneNumber AS phoneNumber,
                   node.placeTypes AS placeTypes,
                   node.googleMapsUrl AS googleMapsUrl,
                   node.editorialSummary AS editorialSummary,
                   node.vicinity AS vicinity,
                   score
            ORDER BY score DESC
            LIMIT $limit
            """

            with self.driver.session() as session:
                result = session.run(cypher, {
                    "embedding": query_embedding,
                    "limit": limit,
                })
                matches = [dict(record) for record in result]

            logger.info(f"Vector search found {len(matches)} results across all cities")
            return matches

        except Exception as e:
            logger.error(f"Vector search (all cities) failed: {e}")
            return []

    # ------------------------------------------------------------------
    # City-based search
    # ------------------------------------------------------------------

    def _get_attractions_by_city(
        self,
        city: str,
        country: str,
        poi_name: Optional[str] = None,
        poi_category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get attractions from Neo4j filtered by city."""
        where_clauses = ["toLower(a.city) = toLower($city)"]
        params: Dict[str, Any] = {"city": city, "limit": limit}

        if poi_name:
            where_clauses.append("toLower(a.title) CONTAINS toLower($poi_name)")
            params["poi_name"] = poi_name

        if poi_category:
            where_clauses.append("toLower(a.placeTypes) CONTAINS toLower($poi_category)")
            params["poi_category"] = poi_category

        where_clause = " AND ".join(where_clauses)

        cypher = f"""
        MATCH (a:Attraction)
        WHERE {where_clause}
        OPTIONAL MATCH (a)-[:LOCATED_IN]->(d:District)
        RETURN a.title AS title,
               a.description AS description,
               a.imageUrl AS imageUrl,
               a.latitude AS latitude,
               a.longitude AS longitude,
               a.formattedAddress AS formattedAddress,
               a.city AS city,
               a.district AS district,
               a.province AS province,
               a.rating AS rating,
               a.userRatingsTotal AS userRatingsTotal,
               a.website AS website,
               a.phoneNumber AS phoneNumber,
               a.priceLevel AS priceLevel,
               a.placeTypes AS placeTypes,
               a.googleMapsUrl AS googleMapsUrl,
               a.editorialSummary AS editorialSummary,
               a.vicinity AS vicinity,
               d.name AS districtNode
        ORDER BY a.rating DESC, a.userRatingsTotal DESC
        LIMIT $limit
        """

        with self.driver.session() as session:
            result = session.run(cypher, params)
            return [dict(record) for record in result]

    # ------------------------------------------------------------------
    # Mapping and formatting
    # ------------------------------------------------------------------

    def _map_to_item(self, data: Dict[str, Any]) -> AttractionItem:
        """Map Neo4j data to ``AttractionItem`` model."""
        category = self._extract_category(data.get("placeTypes"))
        location = self._build_location_string(
            data.get("vicinity"),
            data.get("formattedAddress"),
            data.get("city"),
            data.get("district"),
        )
        open_hours = "Hours vary, please check website"
        entry_fee = self._estimate_entry_fee(data.get("priceLevel"))

        coordinates = None
        if data.get("latitude") and data.get("longitude"):
            coordinates = f"{data['latitude']}, {data['longitude']}"

        return AttractionItem(
            name=data.get("title", "Unknown Attraction"),
            category=category,
            description=data.get("description") or data.get("editorialSummary"),
            location=location,
            open_hours=open_hours,
            entry_fee_lkr=entry_fee,
            source="kg_service",
            rating=data.get("rating"),
            coordinates=coordinates,
            website=data.get("website"),
            phone=data.get("phoneNumber"),
        )

    @staticmethod
    def _extract_category(place_types: Optional[str]) -> Optional[str]:
        """Extract primary category from place types string."""
        if not place_types:
            return None

        _CATEGORY_KEYWORDS = {
            "temple": "temple",
            "church": "religious site",
            "mosque": "religious site",
            "museum": "museum",
            "park": "park",
            "garden": "garden",
            "zoo": "zoo",
            "beach": "beach",
            "historical": "historical site",
            "monument": "monument",
            "palace": "palace",
            "fort": "fort",
            "waterfall": "natural attraction",
            "lake": "natural attraction",
            "mountain": "natural attraction",
            "viewpoint": "viewpoint",
            "market": "market",
            "shopping": "shopping",
            "restaurant": "dining",
            "hotel": "accommodation",
        }

        place_types_lower = place_types.lower()
        for keyword, category in _CATEGORY_KEYWORDS.items():
            if keyword in place_types_lower:
                return category

        return "attraction"

    @staticmethod
    def _build_location_string(
        vicinity: Optional[str],
        formatted_address: Optional[str],
        city: Optional[str],
        district: Optional[str],
    ) -> Optional[str]:
        """Build location string from available data."""
        if vicinity:
            return vicinity
        if formatted_address:
            return formatted_address
        if city and district:
            return f"{city}, {district}"
        if city:
            return city
        return None

    @staticmethod
    def _estimate_entry_fee(price_level: Optional[int]) -> Optional[str]:
        """Estimate entry fee from Google price level (0-4)."""
        if price_level is None:
            return "Contact for pricing"

        _FEE_ESTIMATES = {
            0: "Free",
            1: "500-1000",
            2: "1000-2000",
            3: "2000-4000",
            4: "4000+",
        }
        return _FEE_ESTIMATES.get(price_level, "Contact for pricing")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_summary(
        items: List[AttractionItem],
        city: str,
        days: Optional[int] = None,
    ) -> str:
        """Generate natural language summary of search results."""
        if not items:
            location = f"in {city}" if city and city != "Sri Lanka" else "matching your criteria"
            return f"No attractions found {location}."

        count = len(items)
        categories: Dict[str, int] = {}
        cities_found: set = set()
        
        for item in items:
            cat = item.category or "attraction"
            categories[cat] = categories.get(cat, 0) + 1
            if item.location:
                # Try to extract city from location string
                cities_found.add(item.location.split(",")[0].strip())

        top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
        cat_text = ", ".join(
            f"{c} {name}{'s' if c > 1 else ''}" for name, c in top_cats
        )

        # Determine location text for summary
        if city and city != "Sri Lanka":
            location_text = f"in {city}"
        elif len(cities_found) > 1:
            location_text = f"across {len(cities_found)} cities"
        else:
            location_text = "in Sri Lanka"

        summary = f"Found {count} attraction{'s' if count != 1 else ''} {location_text}"
        if cat_text:
            summary += f" including {cat_text}"

        if days:
            if days == 1:
                summary += ". Perfect for a day trip."
            elif days <= 3:
                summary += f". Enough variety for a {days}-day visit."
            else:
                summary += f". Great selection for a {days}-day exploration."

        return summary + "."
