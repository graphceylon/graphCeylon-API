"""
Orchestrator Transport Service

Business logic for transport search functionality used by orchestrator service.
"""

import logging

from typing import List, Dict, Any

from aiohttp import request
from neo4j import Driver

from core.utils import normalize_location_name, STATION_ALIASES
from models.domain.railway import (
    TransportSearchRequest,
    TransportOption,
    TransportSearchResponse,
)
import os
# from services.orchestrator.src.orchestrator_core.orchestrator_service import _SCHEDULE_DATE

logger = logging.getLogger(__name__)
_SCHEDULE_DATE: str = os.getenv("RAILWAY_SCHEDULE_DATE", "2026-01-09")

# Scenic routes for enriching summaries
_SCENIC_ROUTES: Dict[tuple, str] = {
    ("colombo fort", "kandy"): "scenic hill country train route",
    ("colombo fort", "badulla"): "scenic hill country train route through Ella",
    ("colombo fort", "galle"): "coastal train route",
    ("colombo fort", "matara"): "southern coastal train route",
}

CITY_TO_STATION: Dict[str, str] = {
    "colombo": "Colombo Fort",
    "kandy": "Kandy",
    "galle": "Galle",
    "ella": "Ella",
    "badulla": "Badulla",
    "jaffna": "Jaffna",
    "matara": "Matara",
    "gampaha": "Gampaha",
    "kurunegala": "Kurunegala",
    "anuradhapura": "Anuradhapura",
    "trincomalee": "Trincomalee",
    "batticaloa": "Batticaloa",
    "nuwara eliya": "Nanu Oya",
    "bandarawela": "Bandarawela",
    "haputale": "Haputale",
    "peradeniya": "Peradeniya",
    "vavuniya": "Vavuniya",
    "polonnaruwa": "Polonnaruwa",
    "beliaththa": "Beliaththa",
}
class OrchestratorTransportService:
    """Service for handling orchestrator transport search requests."""

    def __init__(self, driver: Driver):
        self.driver = driver

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_station(city: str) -> str:
        """Map city name to actual station name stored in Neo4j."""
        return CITY_TO_STATION.get((city or "").strip().lower(), city)
    def search_transport(self, request: TransportSearchRequest) -> TransportSearchResponse:
        try:
            origin      = self._resolve_station(normalize_location_name(request.origin, STATION_ALIASES))
            destination = self._resolve_station(normalize_location_name(request.destination, STATION_ALIASES))
            print(f"[transport] raw origin={request.origin!r} → resolved={origin!r}")
            print(f"[transport] raw dest={request.destination!r} → resolved={destination!r}")
            print(f"[transport] schedule_date={_SCHEDULE_DATE!r}")

            train_options = self._get_train_options(origin, destination, request)
            print(f"[transport] options found: {len(train_options)}")

            summary = self._generate_summary(train_options, origin, destination)

            if not train_options:
                return TransportSearchResponse(
                    ok=False,
                    origin=request.origin,
                    destination=request.destination,
                    country=request.country,
                    options=[],
                    summary="",
                    error="No routes found",
                    details=f"No transport options available between {request.origin} and {request.destination}",
                )

            return TransportSearchResponse(
                ok=True,
                origin=request.origin,
                destination=request.destination,
                country=request.country,
                options=train_options,
                summary=summary,
            )

        except Exception as e:
            return TransportSearchResponse(
                ok=False,
                origin=request.origin,
                destination=request.destination,
                country=request.country,
                options=[],
                summary="",
                error="Transport search failed",
                details=str(e),
            )

    # ------------------------------------------------------------------
    # Train options
    # ------------------------------------------------------------------

    # def _get_train_options(
    #     self,
    #     origin: str,
    #     destination: str,
    #     request: TransportSearchRequest,
    # ) -> List[TransportOption]:
    #     """Get train route options from Neo4j."""
    #     options: list[TransportOption] = []

    #     try:
    #         # Use request date if provided, otherwise query without date filter
    #         schedule_date = getattr(request, "schedule_date", None) or None

    #         cypher = """
    #         MATCH (start:RailwayStation)<-[:DEPARTS_FROM]-(schedule:TrainSchedule)-[:ARRIVES_AT]->(end:RailwayStation)
    #         WHERE toLower(start.name) = toLower($origin)
    #         AND toLower(end.name) = toLower($destination)
    #         AND ($schedule_date IS NULL OR schedule.schedule_date = $schedule_date)
    #         RETURN properties(schedule) as schedule,
    #             start.name as start_station,
    #             end.name as end_station
    #         ORDER BY schedule.departure_time
    #         LIMIT 5
    #         """
    #         with self.driver.session() as session:
    #             result = session.run(cypher, {
    #                 "origin": origin,
    #                 "destination": destination,
    #                 "schedule_date": schedule_date,
    #             })

    #             schedules = [record["schedule"] for record in result]
    #             if not schedules:
    #                 return options

    #             train_types_seen: set[str] = set()

    #             for sched in schedules:
    #                 train_type = sched.get("train_type", "Slow")
    #                 if train_type in train_types_seen:
    #                     continue
    #                 train_types_seen.add(train_type)

    #                 duration_min = self._parse_duration_to_minutes(
    #                     sched.get("duration", "0h 0m")
    #                 )
    #                 cost_lkr = self._parse_price_to_float(
    #                     sched.get("price_3rd_class", "Rs. 0")
    #                 )

    #                 departure_time = sched.get("departure_time", "")
    #                 arrival_time = sched.get("arrival_time", "")

    #                 summary = self._generate_train_summary(
    #                     origin, destination, train_type, departure_time, arrival_time
    #                 )
    #                 tips = self._generate_train_tips(train_type, duration_min)

    #                 options.append(
    #                     TransportOption(
    #                         mode="train",
    #                         summary=summary,
    #                         estimated_time_min=duration_min,
    #                         estimated_cost_lkr=cost_lkr,
    #                         tips=tips,
    #                         source="Sri Lanka Railways",
    #                     )
    #                 )

    #     except Exception as e:
    #         logger.error(f"Error getting train options: {e}")

    #     return options

    def _get_train_options(
        self,
        origin: str,
        destination: str,
        request: TransportSearchRequest,
    ) -> List[TransportOption]:
        options: list[TransportOption] = []

        try:
            schedule_date = _SCHEDULE_DATE

            with self.driver.session() as session:

                # Strategy 1: relationship traversal (correct pattern for this schema)
                result = session.run("""
                    MATCH (start:RailwayStation)<-[:DEPARTS_FROM]-(s:TrainSchedule)-[:ARRIVES_AT]->(end:RailwayStation)
                    WHERE toLower(start.name) = toLower($origin)
                    AND toLower(end.name) = toLower($destination)
                    AND s.schedule_date = $schedule_date
                    RETURN properties(s) AS schedule,
                        start.name AS start_name,
                        end.name   AS end_name
                    ORDER BY s.departure_time
                """, {"origin": origin, "destination": destination, "schedule_date": schedule_date})

                seen_trains: set[str] = set()
                schedules: list[dict] = []
                for record in result:
                    s = dict(record["schedule"])
                    tnum = s.get("train_number") or ""
                    if tnum and tnum in seen_trains:
                        continue
                    if tnum:
                        seen_trains.add(tnum)
                    schedules.append(s)

                print(f"[transport] strategy1 (relationships) found {len(schedules)} unique schedules")

                # Strategy 2: destination station name contains the search term
                # (handles "Nanu Oya" for "Nuwara Eliya" etc.)
                if not schedules:
                    result = session.run("""
                        MATCH (start:RailwayStation)<-[:DEPARTS_FROM]-(s:TrainSchedule)-[:ARRIVES_AT]->(end:RailwayStation)
                        WHERE toLower(start.name) = toLower($origin)
                        AND toLower(end.name) CONTAINS toLower($destination)
                        AND s.schedule_date = $schedule_date
                        RETURN properties(s) AS schedule,
                            start.name AS start_name,
                            end.name   AS end_name
                        ORDER BY s.departure_time
                    """, {"origin": origin, "destination": destination, "schedule_date": schedule_date})

                    seen_trains = set()
                    for record in result:
                        s = dict(record["schedule"])
                        tnum = s.get("train_number") or ""
                        if tnum and tnum in seen_trains:
                            continue
                        if tnum:
                            seen_trains.add(tnum)
                        schedules.append(s)

                    print(f"[transport] strategy2 (contains) found {len(schedules)} unique schedules")

                # Strategy 3: fallback — any schedule departing from origin
                # gives first/last train info even if destination not found
                if not schedules:
                    result = session.run("""
                        MATCH (start:RailwayStation)<-[:DEPARTS_FROM]-(s:TrainSchedule)
                        WHERE toLower(start.name) = toLower($origin)
                        AND s.schedule_date = $schedule_date
                        RETURN properties(s) AS schedule
                        LIMIT 1
                    """, {"origin": origin, "schedule_date": schedule_date})

                    any_sched = [dict(r["schedule"]) for r in result]
                    if any_sched:
                        route_key = (origin.lower(), destination.lower())
                        desc = _SCENIC_ROUTES.get(route_key, "train route")
                        first = any_sched[0].get("first_train_time") or ""
                        last  = any_sched[0].get("last_train_time") or ""
                        tip   = " ".join(filter(None, [first, last, "Book at eservices.railway.gov.lk"])).strip()
                        options.append(TransportOption(
                            mode="train",
                            summary=f"{origin} to {destination} — {desc}",
                            estimated_time_min=180,
                            estimated_cost_lkr=300.0,
                            tips=tip,
                            source="Sri Lanka Railways",
                        ))
                    print(f"[transport] strategy3 (fallback) used")
                    return options

                # Build TransportOption per unique schedule
                for sched in schedules:
                    duration_min = self._parse_duration_to_minutes(sched.get("duration") or "0h 0m")
                    cost_lkr     = self._parse_price_to_float(sched.get("price_3rd_class") or "Rs. 0")
                    dep          = sched.get("departure_time") or ""
                    arr          = sched.get("arrival_time") or ""
                    train_type   = sched.get("train_type") or "Express"
                    train_num    = sched.get("train_number") or ""

                    route_key     = (origin.lower(), destination.lower())
                    scenic        = _SCENIC_ROUTES.get(route_key, "")
                    scenic_suffix = f" ({scenic})" if scenic else ""
                    dep_str       = f"departs {dep}" if dep else ""
                    arr_str       = f"arrives {arr}" if arr else ""
                    time_str      = f"{dep_str} → {arr_str}".strip(" →").strip()
                    summary       = f"Train {train_num} ({train_type}) — {time_str}{scenic_suffix}"

                    first = sched.get("first_train_time") or ""
                    last  = sched.get("last_train_time") or ""
                    tips  = self._generate_train_tips(train_type, duration_min)
                    if first or last:
                        tips = f"{tips}. {first} {last}".strip(". ")

                    options.append(TransportOption(
                        mode="train",
                        summary=summary,
                        estimated_time_min=duration_min,
                        estimated_cost_lkr=cost_lkr,
                        tips=tips,
                        source="Sri Lanka Railways",
                    ))

        except Exception as e:
            logger.error(f"[transport] error: {e}", exc_info=True)

        return options
    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_duration_to_minutes(duration_str: str) -> int:
        """Parse duration string like ``3h 30m`` to total minutes."""
        try:
            hours = minutes = 0
            for part in duration_str.lower().split():
                if "h" in part:
                    hours = int(part.replace("h", ""))
                elif "m" in part:
                    minutes = int(part.replace("m", ""))
            return hours * 60 + minutes
        except (ValueError, AttributeError):
            return 0

    @staticmethod
    def _parse_price_to_float(price_str: str) -> float:
        """Parse price string like ``Rs. 300.00`` to float."""
        try:
            return float(price_str.replace("Rs.", "").replace(",", "").strip())
        except (ValueError, AttributeError):
            return 0.0

    # ------------------------------------------------------------------
    # Summary generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_train_summary(
        origin: str,
        destination: str,
        train_type: str,
        departure_time: str,
        arrival_time: str,
    ) -> str:
        """Generate descriptive summary for a train option."""
        route_key = (origin.lower(), destination.lower())
        special_desc = _SCENIC_ROUTES.get(route_key, "train route")

        tt = train_type.lower()
        if tt in ("express", "intercity"):
            return f"{origin} to {destination} {tt} {special_desc}"
        return f"{origin} to {destination} {special_desc}"

    @staticmethod
    def _generate_train_tips(train_type: str, duration_min: int) -> str:
        """Generate travel tips based on train type and duration."""
        tips: list[str] = []

        tt = train_type.lower()
        if tt == "express":
            tips.append("Reserve seats in advance for Express trains")
        elif tt == "intercity":
            tips.append("Intercity trains offer air-conditioned coaches")
        else:
            tips.append("Slow trains stop at all stations")

        if duration_min > 180:
            tips.append("bring snacks and water for the journey")

        return "; ".join(tips) if tips else "Book tickets early during peak season"

    @staticmethod
    def _generate_summary(
        options: List[TransportOption],
        origin: str,
        destination: str,
    ) -> str:
        """Generate overall summary comparing all transport options."""
        if not options:
            return f"No transport options found between {origin} and {destination}"

        if len(options) == 1:
            opt = options[0]
            return f"{opt.mode.title()} available with {opt.estimated_time_min // 60}h journey time"

        fastest = min(options, key=lambda x: x.estimated_time_min)
        cheapest = min(options, key=lambda x: x.estimated_cost_lkr)

        parts: list[str] = []

        train_opt = next((o for o in options if o.mode == "train"), None)
        if train_opt and "scenic" in train_opt.summary.lower():
            parts.append("Train is the most scenic option")

        if fastest.mode != cheapest.mode:
            parts.append(f"{fastest.mode} is fastest ({fastest.estimated_time_min // 60}h)")
            parts.append(
                f"{cheapest.mode} is most economical (Rs. {cheapest.estimated_cost_lkr:.0f})"
            )

        return "; ".join(parts) if parts else "Multiple transport options available"
