"""
Orchestrator Sub-Attraction Service

Business logic for sub-attraction (POI) search functionality.
Provides intelligent search across sub-attractions within parent locations.

The request/response contract mirrors OrchestratorAttractionService so the
orchestrator can call both endpoints uniformly.
"""

import json
import logging
from typing import List, Dict, Any, Optional

from neo4j import Driver

from core.utils import normalize_location_name, CITY_ALIASES
from models.domain.sub_attraction import (
    SubAttractionSearchRequest,
    SubAttractionItem,
    SubAttractionSearchResponse,
)

logger = logging.getLogger(__name__)


# Maps Google / OSM type tokens to human-readable categories
_CATEGORY_KEYWORDS = {
    "temple": "temple",
    "place_of_worship": "religious site",
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
    "peak": "natural attraction",
    "cave": "natural attraction",
    "market": "market",
    "supermarket": "shopping",
    "department_store": "shopping",
    "shopping": "shopping",
    "restaurant": "dining",
    "cafe": "cafe",
    "fast_food": "dining",
    "bakery": "food & bakery",
    "hotel": "accommodation",
    "school": "education",
    "bank": "finance",
    "attraction": "attraction",
    "tourist_attraction": "attraction",
}

# Entry fee estimates from Google price level (0-4)
_FEE_ESTIMATES = {
    0: "Free",
    1: "500-1000",
    2: "1000-2000",
    3: "2000-4000",
    4: "4000+",
}


class OrchestratorSubAttractionService:
    """Service for handling orchestrator sub-attraction search requests.

    Mirrors the contract of ``OrchestratorAttractionService`` so the
    orchestrator can call ``/orchestrator/call/sub-attractions`` with the
    same payload shape used for ``/orchestrator/call/attractions``.
    """

    def __init__(self, driver: Driver):
        self.driver = driver

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_sub_attractions(
        self,
        request: SubAttractionSearchRequest,
        rejected_categories: Optional[List[str]] = None,
    ) -> SubAttractionSearchResponse:
        """Search sub-attractions using the same strategy pattern as attractions.

        1. City only (no preferred_poi_category): Direct city-based search
        2. City + preferred_poi_category: Filtered by parent location + category
        3. preferred_poi_category only: Search across all cities
        4. poi_name: Filter by specific POI name
        5. rejected_categories: Excluded before applying any other category filter
        """
        try:
            city = ""
            if request.city:
                city = normalize_location_name(request.city, CITY_ALIASES)

            results = self._get_sub_attractions(
                city=city,
                country=request.country,
                poi_name=request.poi_name,
                preferred_poi_category=request.preferred_poi_category,
                rejected_categories=rejected_categories or [],
                tags=request.tags,
                limit=10,
            )

            items = [self._map_to_item(r) for r in results]

            summary = self._generate_summary(
                items=items,
                city=city or (request.city or ""),
                days=request.days,
            )

            return SubAttractionSearchResponse(
                ok=True,
                city=city or request.city or "all",
                country=request.country,
                items=items,
                summary=summary,
            )

        except Exception as e:
            logger.error(f"Sub-attraction search failed: {e}")
            return SubAttractionSearchResponse(
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

    def _get_sub_attractions(
        self,
        city: str = "",
        country: str = "Sri Lanka",
        poi_name: Optional[str] = None,
        preferred_poi_category: Optional[str] = None,
        rejected_categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Fetch sub-attractions from Neo4j with filters.

        Filtering order:
        1. ``rejected_categories`` (passed from caller) are excluded first.
        2. Then include only sub-attractions matching ``preferred_poi_category``.
        """

        _CATEGORY_FIELDS = (
            "s.groups", "s.amenityType", "s.shopType", "s.tourismType",
            "s.naturalType", "s.historicType", "s.primaryType",
            "s.placeTypes", "s.religion",
        )

        where_clauses: List[str] = []
        params: Dict[str, Any] = {"limit": limit}

        # City filter – match via sub-attraction city, parentLocation, district, or province
        if city:
            where_clauses.append(
                "(toLower(s.city) = toLower($city) "
                "OR toLower(s.parentLocation) = toLower($city) "
                "OR toLower(s.district) = toLower($city) "
                "OR toLower(s.province) = toLower($city))"
            )
            params["city"] = city

        # POI name filter
        if poi_name:
            where_clauses.append("toLower(s.name) CONTAINS toLower($poiName)")
            params["poiName"] = poi_name

        # --- Step 1: Rejection filter (list passed in from router) ---
        for idx, rejected in enumerate(rejected_categories or []):
            reject_param = f"rejected{idx}"
            reject_conditions = " OR ".join(
                f"toLower({f}) CONTAINS toLower(${reject_param})"
                for f in _CATEGORY_FIELDS
            )
            where_clauses.append(f"NOT ({reject_conditions})")
            params[reject_param] = rejected

        # --- Step 2: Preferred category filter (applied after rejection) ---
        if preferred_poi_category and preferred_poi_category.strip():
            prefer_conditions = " OR ".join(
                f"toLower({f}) CONTAINS toLower($preferredPoiCategory)"
                for f in _CATEGORY_FIELDS
            )
            where_clauses.append(f"({prefer_conditions})")
            params["preferredPoiCategory"] = preferred_poi_category.strip()

        # Tags filter (match any tag against groups / placeTypes / religion)
        if tags:
            tag_clauses = []
            for i, tag in enumerate(tags):
                tag_param = f"tag{i}"
                tag_clauses.append(
                    f"(toLower(s.groups) CONTAINS toLower(${tag_param}) "
                    f"OR toLower(s.placeTypes) CONTAINS toLower(${tag_param}) "
                    f"OR toLower(s.religion) CONTAINS toLower(${tag_param}))"
                )
                params[tag_param] = tag
            if tag_clauses:
                where_clauses.append(f"({' OR '.join(tag_clauses)})")

        # Exclude closed businesses
        where_clauses.append(
            "(s.businessStatus IS NULL OR s.businessStatus = '' "
            "OR s.businessStatus = 'OPERATIONAL')"
        )

        where_clause = " AND ".join(where_clauses) if where_clauses else "true"

        cypher = f"""
        MATCH (s:SubAttraction)
        OPTIONAL MATCH (s)-[:SUB_ATTRACTION_OF]->(a:Attraction)
        WITH s, a
        WHERE {where_clause}
        OPTIONAL MATCH (s)-[:LOCATED_IN]->(d:District)
        OPTIONAL MATCH (d)-[:IN_PROVINCE]->(p:Province)
        OPTIONAL MATCH (s)-[:BELONGS_TO_GROUP]->(grp:POIGroup)
        RETURN s.name AS name,
               s.parentLocation AS parentLocation,
               a.title AS parentAttraction,
               s.latitude AS latitude,
               s.longitude AS longitude,
               s.amenityType AS amenityType,
               s.shopType AS shopType,
               s.tourismType AS tourismType,
               s.naturalType AS naturalType,
               s.historicType AS historicType,
               s.primaryType AS primaryType,
               s.religion AS religion,
               s.cuisine AS cuisine,
               s.brand AS brand,
               s.rating AS rating,
               s.userRatingsTotal AS userRatingsTotal,
               s.priceLevel AS priceLevel,
               s.formattedAddress AS formattedAddress,
               s.vicinity AS vicinity,
               s.website AS website,
               s.phone AS phone,
               s.internationalPhone AS internationalPhone,
               s.editorialSummary AS editorialSummary,
               s.placeTypes AS placeTypes,
               s.weekdayText AS weekdayText,
               s.openingHours AS openingHours,
               s.googleMapsUrl AS googleMapsUrl,
               s.businessStatus AS businessStatus,
               d.name AS district,
               p.name AS province,
               s.city AS city,
               collect(DISTINCT grp.name) AS poiGroups
        ORDER BY coalesce(s.rating, 0) DESC, coalesce(s.userRatingsTotal, 0) DESC
        LIMIT $limit
        """

        with self.driver.session() as session:
            result = session.run(cypher, params)
            return [record.data() for record in result]

    # ------------------------------------------------------------------
    # Mapping  (mirror of OrchestratorAttractionService._map_to_item)
    # ------------------------------------------------------------------

    def _map_to_item(self, data: Dict[str, Any]) -> SubAttractionItem:
        """Map a Neo4j record to ``SubAttractionItem``."""

        category = self._extract_category(data)
        location = self._build_location_string(data)
        open_hours = self._extract_open_hours(data)
        entry_fee = _FEE_ESTIMATES.get(data.get("priceLevel"), "Contact for pricing")

        coordinates = None
        if data.get("latitude") and data.get("longitude"):
            coordinates = f"{data['latitude']}, {data['longitude']}"

        description = data.get("editorialSummary") or None

        city = data.get("city") or data.get("parentLocation") or None
        district = data.get("district") or None
        province = data.get("province") or None
        groups = data.get("poiGroups") or None

        return SubAttractionItem(
            name=data.get("name", "Unknown POI"),
            category=category,
            description=description,
            location=location,
            city=city,
            district=district,
            province=province,
            groups=groups,
            open_hours=open_hours,
            entry_fee_lkr=entry_fee,
            source="kg_service",
            rating=data.get("rating"),
            coordinates=coordinates,
            website=data.get("website") or None,
            phone=data.get("internationalPhone") or data.get("phone") or None,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_category(data: Dict[str, Any]) -> Optional[str]:
        """Derive a human-readable category from type fields and Google place types."""

        # Collect all type tokens into one searchable string
        type_parts = [
            data.get("amenityType", ""),
            data.get("shopType", ""),
            data.get("tourismType", ""),
            data.get("naturalType", ""),
            data.get("historicType", ""),
            data.get("primaryType", ""),
            data.get("religion", ""),
            data.get("placeTypes", ""),
        ]
        combined = " ".join(t for t in type_parts if t).lower()

        for keyword, category in _CATEGORY_KEYWORDS.items():
            if keyword in combined:
                # Prefix with religion when relevant
                religion = data.get("religion", "")
                if religion and category in ("temple", "religious site"):
                    return f"{religion} {category}"
                return category

        # Fallback to POI group
        groups = data.get("poiGroups", [])
        if groups:
            return groups[0].lower()

        return "attraction"

    @staticmethod
    def _build_location_string(data: Dict[str, Any]) -> Optional[str]:
        """Build a human-readable location string."""
        if data.get("vicinity"):
            return data["vicinity"]
        if data.get("formattedAddress"):
            return data["formattedAddress"]
        city = data.get("city") or data.get("parentLocation") or ""
        district = data.get("district") or ""
        if city and district:
            return f"{city}, {district}"
        return city or district or None

    @staticmethod
    def _extract_open_hours(data: Dict[str, Any]) -> Optional[str]:
        """Extract concise opening hours string."""
        raw = data.get("weekdayText")
        if raw:
            try:
                texts = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(texts, list) and texts:
                    # Return first entry as representative (e.g., "Monday: 8:00 AM – 11:00 PM")
                    # Try to find a common pattern like "8:00 AM – 11:00 PM"
                    first = texts[0] if texts else ""
                    if ": " in first:
                        time_part = first.split(": ", 1)[1]
                        # Check if all days share the same hours
                        all_same = all(
                            t.split(": ", 1)[1] == time_part
                            for t in texts
                            if ": " in t
                        )
                        if all_same:
                            return time_part
                    return "; ".join(texts[:2]) + (" ..." if len(texts) > 2 else "")
            except (json.JSONDecodeError, TypeError, IndexError):
                pass

        return "Hours vary, please check website"

    @staticmethod
    def _generate_summary(
        items: List[SubAttractionItem],
        city: str,
        days: Optional[int] = None,
    ) -> str:
        """Generate natural language summary matching attraction service style."""
        if not items:
            location = f"in {city}" if city else "matching your criteria"
            return f"No sub-attractions found {location}."

        count = len(items)
        categories: Dict[str, int] = {}
        for item in items:
            cat = item.category or "attraction"
            categories[cat] = categories.get(cat, 0) + 1

        top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
        cat_text = ", ".join(
            f"{c} {name}{'s' if c > 1 else ''}" for name, c in top_cats
        )

        location_text = f"in {city}" if city and city not in ("all", "") else "in Sri Lanka"
        summary = f"Found {count} point{'s' if count != 1 else ''} of interest {location_text}"
        if cat_text:
            summary += f" including {cat_text}"

        if days:
            if days == 1:
                summary += ". Perfect for a day trip"
            elif days <= 3:
                summary += f". Enough variety for a {days}-day visit"
            else:
                summary += f". Great selection for a {days}-day exploration"

        return summary + "."
