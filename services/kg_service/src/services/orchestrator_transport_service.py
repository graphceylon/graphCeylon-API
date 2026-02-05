"""
Orchestrator Transport Service

Business logic for transport search functionality used by orchestrator service
"""

from typing import List, Dict, Any
import time
from datetime import datetime
from neo4j import Driver

from models.domain.transport_orchestrator import (
    TransportSearchRequest,
    TransportOption,
    TransportSearchResponse
)


class OrchestratorTransportService:
    """Service for handling orchestrator transport search requests"""
    
    def __init__(self, driver: Driver):
        """
        Initialize service with Neo4j driver
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
    
    def search_transport(self, request: TransportSearchRequest) -> TransportSearchResponse:
        """
        Search transport options between origin and destination
        
        Currently supports:
        - Train routes (from Neo4j railway data)
        
        Args:
            request: TransportSearchRequest with search criteria
            
        Returns:
            TransportSearchResponse with transport options or error
        """
        try:
            # Normalize station names
            origin = self._normalize_station_name(request.origin)
            destination = self._normalize_station_name(request.destination)
            
            # Get train options
            train_options = self._get_train_options(origin, destination, request)
            
            # Combine all options
            all_options = train_options
            
            # Generate summary
            summary = self._generate_summary(all_options, origin, destination)
            
            # If no options found, return helpful error
            if not all_options:
                return TransportSearchResponse(
                    ok=False,
                    origin=request.origin,
                    destination=request.destination,
                    country=request.country,
                    options=[],
                    summary="",
                    error="No routes found",
                    details=f"No transport options available between {request.origin} and {request.destination}"
                )
            
            return TransportSearchResponse(
                ok=True,
                origin=request.origin,
                destination=request.destination,
                country=request.country,
                options=all_options,
                summary=summary
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
                details=str(e)
            )
    
    def _normalize_station_name(self, name: str) -> str:
        """
        Normalize station names for better matching
        
        Examples:
        - "Colombo" -> "Colombo Fort"
        - "colombo fort" -> "Colombo Fort"
        """
        name_lower = name.lower().strip()
        
        # Common aliases
        station_aliases = {
            "colombo": "Colombo Fort",
            "fort": "Colombo Fort",
            "kandy": "Kandy",
            "galle": "Galle",
            "matara": "Matara",
            "jaffna": "Jaffna",
            "anuradhapura": "Anuradhapura",
            "batticaloa": "Batticaloa",
            "trincomalee": "Trincomalee",
            "badulla": "Badulla",
            "ella": "Ella",
        }
        
        # Check if name matches an alias
        if name_lower in station_aliases:
            return station_aliases[name_lower]
        
        # Otherwise return title-cased version
        return name.title()
    
    def _get_train_options(
        self,
        origin: str,
        destination: str,
        request: TransportSearchRequest
    ) -> List[TransportOption]:
        """
        Get train route options from Neo4j
        
        Args:
            origin: Starting station
            destination: Ending station
            request: Original request for filtering
            
        Returns:
            List of TransportOption for trains
        """
        options = []
        
        try:
            # Use database date (all schedules are for 2026-01-09)
            # TODO: Make this configurable or query latest available date dynamically
            schedule_date = "2026-01-09"
            
            # Query train schedules using relationships
            cypher = """
            MATCH (start:RailwayStation)<-[:DEPARTS_FROM]-(schedule:TrainSchedule)-[:ARRIVES_AT]->(end:RailwayStation)
            WHERE toLower(start.name) = toLower($origin)
              AND toLower(end.name) = toLower($destination)
              AND schedule.schedule_date = $schedule_date
            RETURN properties(schedule) as schedule,
                   start.name as start_station,
                   end.name as end_station
            ORDER BY schedule.departure_time
            LIMIT 5
            """
            
            with self.driver.session() as session:
                result = session.run(cypher, {
                    "origin": origin,
                    "destination": destination,
                    "schedule_date": schedule_date
                })
                
                schedules = [record["schedule"] for record in result]
                
                if schedules:
                    # Group by train type for better presentation
                    train_types_seen = set()
                    
                    for schedule_node in schedules:
                        train_type = schedule_node.get("train_type", "Slow")
                        
                        # Only include one option per train type
                        if train_type in train_types_seen:
                            continue
                        train_types_seen.add(train_type)
                        
                        # Parse duration (format: "3h 30m")
                        duration_str = schedule_node.get("duration", "0h 0m")
                        duration_min = self._parse_duration_to_minutes(duration_str)
                        
                        # Parse price (format: "Rs. 300.00")
                        price_str = schedule_node.get("price_3rd_class", "Rs. 0")
                        cost_lkr = self._parse_price_to_float(price_str)
                        
                        # Get train details
                        train_number = schedule_node.get("train_number", "")
                        departure_time = schedule_node.get("departure_time", "")
                        arrival_time = schedule_node.get("arrival_time", "")
                        
                        # Generate summary
                        summary = self._generate_train_summary(
                            origin,
                            destination,
                            train_type,
                            departure_time,
                            arrival_time
                        )
                        
                        # Generate tips
                        tips = self._generate_train_tips(train_type, duration_min)
                        
                        option = TransportOption(
                            mode="train",
                            summary=summary,
                            estimated_time_min=duration_min,
                            estimated_cost_lkr=cost_lkr,
                            tips=tips,
                            source="Sri Lanka Railways"
                        )
                        
                        options.append(option)
                
        except Exception as e:
            # Log error but don't fail the entire request
            print(f"Error getting train options: {e}")
        
        return options
    
    def _parse_duration_to_minutes(self, duration_str: str) -> int:
        """
        Parse duration string to minutes
        
        Args:
            duration_str: Duration like "3h 30m" or "2h 15m"
            
        Returns:
            Total minutes
        """
        try:
            hours = 0
            minutes = 0
            
            parts = duration_str.lower().split()
            for part in parts:
                if 'h' in part:
                    hours = int(part.replace('h', ''))
                elif 'm' in part:
                    minutes = int(part.replace('m', ''))
            
            return (hours * 60) + minutes
        except:
            return 0
    
    def _parse_price_to_float(self, price_str: str) -> float:
        """
        Parse price string to float
        
        Args:
            price_str: Price like "Rs. 300.00" or "Rs. 1,200.00"
            
        Returns:
            Price as float
        """
        try:
            # Remove currency symbol and commas
            clean_price = price_str.replace("Rs.", "").replace(",", "").strip()
            return float(clean_price)
        except:
            return 0.0
    
    def _generate_train_summary(
        self,
        origin: str,
        destination: str,
        train_type: str,
        departure_time: str,
        arrival_time: str
    ) -> str:
        """
        Generate descriptive summary for train option
        
        Args:
            origin: Starting station
            destination: Ending station
            train_type: Type of train
            departure_time: Departure time
            arrival_time: Arrival time
            
        Returns:
            Formatted summary string
        """
        # Add scenic/special attributes for popular routes
        scenic_routes = {
            ("colombo fort", "kandy"): "scenic hill country train route",
            ("colombo fort", "badulla"): "scenic hill country train route through Ella",
            ("colombo fort", "galle"): "coastal train route",
            ("colombo fort", "matara"): "southern coastal train route",
        }
        
        route_key = (origin.lower(), destination.lower())
        special_desc = scenic_routes.get(route_key, "train route")
        
        if train_type.lower() == "express":
            return f"{origin} to {destination} express {special_desc}"
        elif train_type.lower() == "intercity":
            return f"{origin} to {destination} intercity {special_desc}"
        else:
            return f"{origin} to {destination} {special_desc}"
    
    def _generate_train_tips(self, train_type: str, duration_min: int) -> str:
        """
        Generate travel tips based on train type and duration
        
        Args:
            train_type: Type of train
            duration_min: Journey duration in minutes
            
        Returns:
            Helpful travel tip
        """
        tips = []
        
        # Type-specific tips
        if train_type.lower() == "express":
            tips.append("Reserve seats in advance for Express trains")
        elif train_type.lower() == "intercity":
            tips.append("Intercity trains offer air-conditioned coaches")
        else:
            tips.append("Slow trains stop at all stations")
        
        # Duration-specific tips
        if duration_min > 180:
            tips.append("bring snacks and water for the journey")
        
        # Combine tips
        return "; ".join(tips) if tips else "Book tickets early during peak season"
    
    def _generate_summary(
        self,
        options: List[TransportOption],
        origin: str,
        destination: str
    ) -> str:
        """
        Generate overall summary comparing all options
        
        Args:
            options: List of transport options
            origin: Starting location
            destination: Ending location
            
        Returns:
            Summary string
        """
        if not options:
            return f"No transport options found between {origin} and {destination}"
        
        if len(options) == 1:
            option = options[0]
            return f"{option.mode.title()} available with {option.estimated_time_min // 60}h journey time"
        
        # Compare options
        fastest = min(options, key=lambda x: x.estimated_time_min)
        cheapest = min(options, key=lambda x: x.estimated_cost_lkr)
        
        summary_parts = []
        
        # Find train option if exists
        train_option = next((opt for opt in options if opt.mode == "train"), None)
        
        if train_option:
            if "scenic" in train_option.summary.lower():
                summary_parts.append("Train is the most scenic option")
        
        if fastest.mode != cheapest.mode:
            summary_parts.append(f"{fastest.mode} is fastest ({fastest.estimated_time_min // 60}h)")
            summary_parts.append(f"{cheapest.mode} is most economical (Rs. {cheapest.estimated_cost_lkr:.0f})")
        
        return "; ".join(summary_parts) if summary_parts else "Multiple transport options available"
