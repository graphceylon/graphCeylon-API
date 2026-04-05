# """
# Orchestrator Bus Schedule Service

# Business logic for bus schedule search used by the orchestrator layer.
# Follows the same orchestrator contract as attractions / transport.
# """

# import logging
# from typing import List

# from neo4j import Driver

# from core.utils import normalize_location_name, CITY_ALIASES
# from models.domain.bus_schedule import (
#     BusSearchRequest,
#     BusSearchItem,
#     BusSearchResponse,
# )

# logger = logging.getLogger(__name__)


# class OrchestratorBusService:
#     """Service for handling orchestrator bus search requests."""

#     def __init__(self, driver: Driver):
#         self.driver = driver

#     # ------------------------------------------------------------------
#     # Public API
#     # ------------------------------------------------------------------

#     def search_bus_schedules(self, request: BusSearchRequest) -> BusSearchResponse:
#         """Search bus options between origin and destination."""
#         try:
#             origin = normalize_location_name(request.origin, CITY_ALIASES)
#             destination = normalize_location_name(request.destination, CITY_ALIASES)

#             items = self._query_schedules(origin, destination, request)

#             if not items:
#                 return BusSearchResponse(
#                     ok=False,
#                     city=request.city,
#                     country=request.country,
#                     items=[],
#                     summary="",
#                     error="No bus routes found",
#                     details=f"No bus services found between {request.origin} and {request.destination}",
#                 )

#             summary = self._build_summary(items, origin, destination)

#             return BusSearchResponse(
#                 ok=True,
#                 city=request.city,
#                 country=request.country,
#                 items=items,
#                 summary=summary,
#             )

#         except Exception as e:
#             logger.error(f"Bus schedule search failed: {e}")
#             return BusSearchResponse(
#                 ok=False,
#                 city=request.city,
#                 country=request.country,
#                 items=[],
#                 summary="",
#                 error="Bus schedule search failed",
#                 details=str(e),
#             )

#     # ------------------------------------------------------------------
#     # Internal
#     # ------------------------------------------------------------------

#     def _query_schedules(
#         self,
#         origin: str,
#         destination: str,
#         request: BusSearchRequest,
#     ) -> List[BusSearchItem]:
#         """Query Neo4j for bus schedules between origin and destination."""
#         items: List[BusSearchItem] = []

#         cypher = """
#         MATCH (bs:BusSchedule)
#         WHERE toLower(bs.origin) = toLower($origin)
#           AND toLower(bs.destination) = toLower($destination)
#         {date_filter}
#         {budget_filter}
#         OPTIONAL MATCH (bs)-[:OPERATED_BY_DEPOT]->(depot:BusDepot)
#         RETURN properties(bs) as schedule, depot.name as depot_name
#         ORDER BY bs.fare, bs.departure_time
#         LIMIT 10
#         """

#         date_filter = "AND bs.schedule_date = $schedule_date" if request.schedule_date else ""

#         # Budget filtering
#         if request.budget_level == "low":
#             budget_filter = "AND bs.fare <= 800"
#         elif request.budget_level == "medium":
#             budget_filter = "AND bs.fare <= 1200"
#         else:
#             budget_filter = ""

#         cypher = cypher.format(date_filter=date_filter, budget_filter=budget_filter)

#         params = {
#             "origin": origin,
#             "destination": destination,
#             "schedule_date": request.schedule_date,
#         }

#         try:
#             with self.driver.session() as session:
#                 result = session.run(cypher, params)
#                 records = list(result)

#                 for record in records:
#                     sched = record["schedule"]
#                     depot = record.get("depot_name") or sched.get("depot_name", "SLTB")

#                     dep_time = sched.get("departure_time", "")
#                     arr_time = sched.get("arrival_time", "")
#                     fare = sched.get("fare")

#                     description = (
#                         f"{sched.get('bus_type', 'Normal')} bus operated by {depot} depot. "
#                         f"Departs {dep_time}, arrives {arr_time}. "
#                         f"{sched.get('seats_available', '?')} seats available."
#                     )

#                     items.append(
#                         BusSearchItem(
#                             name=sched.get("schedule_id", ""),
#                             category="Bus",
#                             description=description,
#                             location=f"{sched.get('origin', origin)} → {sched.get('destination', destination)}",
#                             open_hours=f"{dep_time} → {arr_time}" if dep_time else None,
#                             entry_fee_lkr=fare,
#                             source="SLTB eSeat",
#                             website=sched.get("booking_link"),
#                         )
#                     )

#         except Exception as e:
#             logger.error(f"Error querying bus schedules: {e}")

#         return items

#     # ------------------------------------------------------------------
#     # Summary
#     # ------------------------------------------------------------------

#     @staticmethod
#     def _build_summary(items: List[BusSearchItem], origin: str, destination: str) -> str:
#         """Generate a human-readable summary of results."""
#         count = len(items)
#         fares = [i.entry_fee_lkr for i in items if i.entry_fee_lkr is not None]
#         min_fare = min(fares) if fares else 0
#         max_fare = max(fares) if fares else 0

#         if count == 1:
#             return (
#                 f"1 SLTB bus service found from {origin} to {destination}, "
#                 f"fare LKR {min_fare:.0f}."
#             )

#         parts = [f"{count} SLTB bus services found from {origin} to {destination}"]
#         if min_fare and max_fare:
#             if min_fare == max_fare:
#                 parts.append(f"fare LKR {min_fare:.0f}")
#             else:
#                 parts.append(f"fares range LKR {min_fare:.0f} – {max_fare:.0f}")
#         return ". ".join(parts) + "."
"""
Orchestrator Bus Schedule Service
"""

import logging
from typing import List

from neo4j import Driver

from core.utils import normalize_location_name, CITY_ALIASES
from models.domain.bus_schedule import (
    BusSearchRequest,
    BusSearchItem,
    BusSearchResponse,
)

logger = logging.getLogger(__name__)


class OrchestratorBusService:

    def __init__(self, driver: Driver):
        self.driver = driver

    def search_bus_schedules(self, request: BusSearchRequest) -> BusSearchResponse:
        try:
            origin      = normalize_location_name(request.origin, CITY_ALIASES)
            destination = normalize_location_name(request.destination, CITY_ALIASES)

            # ── 1) Try direct routes first ─────────────────────────
            items = self._query_direct(origin, destination, request)

            # ── 2) Fallback: buses that pass THROUGH destination ───
            if not items:
                logger.info(f"No direct routes {origin}→{destination}, trying via-stop search")
                items = self._query_via_stop(origin, destination, request)

            if not items:
                return BusSearchResponse(
                    ok=False,
                    city=request.city,
                    country=request.country,
                    items=[],
                    summary="",
                    error="No bus routes found",
                    details=f"No bus services found between {request.origin} and {request.destination}",
                )

            summary = self._build_summary(items, origin, destination)
            return BusSearchResponse(
                ok=True,
                city=request.city,
                country=request.country,
                items=items,
                summary=summary,
            )

        except Exception as e:
            logger.error(f"Bus schedule search failed: {e}")
            return BusSearchResponse(
                ok=False,
                city=request.city,
                country=request.country,
                items=[],
                summary="",
                error="Bus schedule search failed",
                details=str(e),
            )

    # ------------------------------------------------------------------
    # Query 1: exact origin → destination match
    # ------------------------------------------------------------------

    def _query_direct(
        self,
        origin: str,
        destination: str,
        request: BusSearchRequest,
    ) -> List[BusSearchItem]:

        date_clause   = "AND bs.schedule_date = $schedule_date" if request.schedule_date else ""
        budget_clause = self._budget_clause(request.budget_level)

        cypher = f"""
        MATCH (bs:BusSchedule)
        WHERE toLower(bs.origin)      = toLower($origin)
          AND toLower(bs.destination) = toLower($destination)
          {date_clause}
          {budget_clause}
        OPTIONAL MATCH (bs)-[:OPERATED_BY_DEPOT]->(depot:BusDepot)
        RETURN properties(bs) AS schedule, depot.name AS depot_name
        ORDER BY bs.fare, bs.departure_time
        LIMIT 10
        """

        params = {
            "origin":        origin,
            "destination":   destination,
            "schedule_date": request.schedule_date,
        }

        return self._run_and_build(cypher, params, origin, destination, route_type="direct")

    # ------------------------------------------------------------------
    # Query 2: buses FROM origin that pass THROUGH destination as a stop
    # ------------------------------------------------------------------

    def _query_via_stop(
        self,
        origin: str,
        destination: str,
        request: BusSearchRequest,
    ) -> List[BusSearchItem]:
        """
        Find buses that depart from origin and have destination
        in their dropping_points_json string (case-insensitive).
        """
        date_clause   = "AND bs.schedule_date = $schedule_date" if request.schedule_date else ""
        budget_clause = self._budget_clause(request.budget_level)

        cypher = f"""
        MATCH (bs:BusSchedule)
        WHERE toLower(bs.origin) = toLower($origin)
          AND toLower(bs.dropping_points_json) CONTAINS toLower($destination)
          {date_clause}
          {budget_clause}
        OPTIONAL MATCH (bs)-[:OPERATED_BY_DEPOT]->(depot:BusDepot)
        RETURN properties(bs) AS schedule, depot.name AS depot_name
        ORDER BY bs.fare, bs.departure_time
        LIMIT 10
        """

        params = {
            "origin":        origin,
            "destination":   destination,
            "schedule_date": request.schedule_date,
        }

        return self._run_and_build(cypher, params, origin, destination, route_type="via_stop")

    # ------------------------------------------------------------------
    # Shared runner
    # ------------------------------------------------------------------

    def _run_and_build(
        self,
        cypher: str,
        params: dict,
        origin: str,
        destination: str,
        route_type: str = "direct",
    ) -> List[BusSearchItem]:

        items: List[BusSearchItem] = []

        try:
            with self.driver.session() as session:
                result  = session.run(cypher, params)
                records = list(result)

                for record in records:
                    sched = record["schedule"]
                    depot = record.get("depot_name") or sched.get("depot_name", "SLTB")

                    dep_time = sched.get("departure_time", "")
                    arr_time = sched.get("arrival_time", "")
                    fare     = sched.get("fare")

                    # For via-stop routes clarify it's not a direct terminal
                    if route_type == "via_stop":
                        via_note = (
                            f"This bus travels from {sched.get('origin')} to "
                            f"{sched.get('destination')} and stops at {destination}. "
                        )
                    else:
                        via_note = ""

                    description = (
                        f"{via_note}"
                        f"{sched.get('bus_type', 'Normal')} bus operated by {depot} depot. "
                        f"Departs {dep_time}, arrives {arr_time}. "
                        f"{sched.get('seats_available', '?')} seats available."
                    )

                    # Try to extract the drop time at destination from dropping_points_json
                    drop_time = self._extract_stop_time(
                        sched.get("dropping_points_json", ""), destination
                    )
                    if drop_time and route_type == "via_stop":
                        description += f" Reaches {destination} around {drop_time}."

                    items.append(
                        BusSearchItem(
                            name=sched.get("schedule_id", ""),
                            category="Bus",
                            description=description,
                            location=f"{sched.get('origin', origin)} → {destination}",
                            open_hours=f"{dep_time} → {drop_time or arr_time}" if dep_time else None,
                            entry_fee_lkr=fare,
                            source="SLTB eSeat",
                            website=sched.get("booking_link"),
                        )
                    )

        except Exception as e:
            logger.error(f"Error running bus query ({route_type}): {e}")

        return items

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _budget_clause(budget_level: str | None) -> str:
        if budget_level == "low":
            return "AND bs.fare <= 800"
        if budget_level == "medium":
            return "AND bs.fare <= 1200"
        return ""

    @staticmethod
    def _extract_stop_time(dropping_points_json: str, destination: str) -> str | None:
        """Parse dropping_points_json string to find arrival time at destination stop."""
        import json
        if not dropping_points_json:
            return None
        try:
            points = json.loads(dropping_points_json) if isinstance(dropping_points_json, str) else dropping_points_json
            dest_lower = destination.lower()
            for point in (points or []):
                if isinstance(point, dict):
                    loc = (point.get("location") or "").lower()
                    if dest_lower in loc or loc in dest_lower:
                        return point.get("time")
        except Exception:
            pass
        return None

    @staticmethod
    def _build_summary(items: List[BusSearchItem], origin: str, destination: str) -> str:
        count    = len(items)
        fares    = [i.entry_fee_lkr for i in items if i.entry_fee_lkr is not None]
        min_fare = min(fares) if fares else 0
        max_fare = max(fares) if fares else 0

        parts = [f"{count} SLTB bus service{'s' if count > 1 else ''} found from {origin} to {destination}"]
        if min_fare and max_fare:
            if min_fare == max_fare:
                parts.append(f"fare LKR {min_fare:.0f}")
            else:
                parts.append(f"fares range LKR {min_fare:.0f} – {max_fare:.0f}")
        return ". ".join(parts) + "."