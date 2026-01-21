"""Repository for holiday-related database operations."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from neo4j import Driver

from .base import BaseRepository


logger = logging.getLogger(__name__)


class HolidayRepository(BaseRepository):
    """Repository for managing holiday data in Neo4j."""
    
    def __init__(self, driver: Driver):
        """Initialize holiday repository."""
        super().__init__(driver)
    
    def initialize_temporal_structure(self, start_year: int = 2020, end_year: int = 2026) -> Dict[str, Any]:
        """Initialize the temporal structure (Year -> Month hierarchy).
        
        Args:
            start_year: Starting year (default: 2020)
            end_year: Ending year (default: 2026)
            
        Returns:
            Dictionary with success status and counts
        """
        try:
            logger.info(f"Initializing temporal structure from {start_year} to {end_year}...")
            
            years_created = 0
            months_created = 0
            
            # Create years
            for year in range(start_year, end_year + 1):
                year_query = """
                MERGE (y:Year {year: $year})
                ON CREATE SET y.created_at = datetime()
                RETURN y.year AS year
                """
                result = self.execute_cypher(year_query, {"year": year})
                if result:
                    years_created += 1
            
            logger.info(f"Created {years_created} year nodes")
            
            # Create months for each year
            month_names = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            
            for year in range(start_year, end_year + 1):
                for month_num in range(1, 13):
                    month_query = """
                    MERGE (m:Month {year: $year, month: $month})
                    ON CREATE SET 
                        m.name = $month_name,
                        m.created_at = datetime()
                    WITH m
                    MATCH (y:Year {year: $year})
                    MERGE (y)-[:HAS_MONTH]->(m)
                    MERGE (m)-[:IN_YEAR]->(y)
                    RETURN m.year AS year, m.month AS month
                    """
                    
                    result = self.execute_cypher(month_query, {
                        "year": year,
                        "month": month_num,
                        "month_name": month_names[month_num - 1]
                    })
                    
                    if result:
                        months_created += 1
            
            logger.info(f"Created {months_created} month nodes")
            
            return {
                "success": True,
                "years_created": years_created,
                "months_created": months_created,
                "year_range": f"{start_year}-{end_year}"
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize temporal structure: {e}")
            raise
    
    def create_holiday(self, holiday_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new holiday and link to temporal structure.
        
        Args:
            holiday_data: Dictionary with holiday properties
            
        Returns:
            Created holiday information
        """
        logger.info(f"Creating holiday: {holiday_data.get('name')}")
        
        # Parse date to extract year, month, day
        start_date = datetime.strptime(holiday_data["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(holiday_data["end_date"], "%Y-%m-%d")
        year = start_date.year
        month = start_date.month
        day = start_date.day
        weekday = start_date.strftime("%A")
        duration = (end_date - start_date).days + 1
        
        # Generate ID
        holiday_id = f"{start_date.strftime('%Y%m%d')}_{holiday_data['name'].lower().replace(' ', '_')}"
        
        cypher = """
        CREATE (h:Holiday {
            id: $id,
            name: $name,
            description: $description,
            start_date: date($start_date),
            end_date: date($end_date),
            duration_days: $duration_days,
            holiday_type: $holiday_type,
            category: $category,
            country: "Sri Lanka",
            country_code: "LK",
            status: "confirmed",
            isPublicHoliday: $is_public_holiday,
            location: $location,
            year: $year,
            month: $month,
            day: $day,
            weekday: $weekday,
            created_at: datetime()
        })
        
        WITH h
        MATCH (m:Month {year: $year, month: $month})
        MERGE (h)-[:IN_MONTH]->(m)
        MERGE (m)-[:HAS_HOLIDAY]->(h)
        
        RETURN id(h) AS node_id, h.id AS holiday_id, h.name AS name
        """
        
        result = self.execute_write(cypher, {
            "id": holiday_id,
            "name": holiday_data["name"],
            "description": holiday_data.get("description"),
            "start_date": holiday_data["start_date"],
            "end_date": holiday_data["end_date"],
            "duration_days": duration,
            "holiday_type": holiday_data["holiday_type"],
            "category": holiday_data["category"],
            "is_public_holiday": holiday_data.get("is_public_holiday", True),
            "location": holiday_data.get("location"),
            "year": year,
            "month": month,
            "day": day,
            "weekday": weekday
        })
        
        return {
            "success": True,
            "holiday_id": result[0]["holiday_id"] if result else holiday_id,
            "node_id": result[0]["node_id"] if result else None,
            "name": holiday_data["name"]
        }
    
    def load_from_json(self, file_path: str = None) -> Dict[str, Any]:
        """Load holidays from JSON file.
        
        Args:
            file_path: Optional path to JSON file. If not provided, uses default location.
            
        Returns:
            Dictionary with success status and statistics
        """
        try:
            import json
            from pathlib import Path
            
            logger.info("Loading holidays from JSON...")
            
            # Use provided path or default
            if file_path is None:
                file_path = str(Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "kg_service" / "data" / "holidays.json")
            
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Holidays data file not found: {file_path}")
            
            # Load JSON data
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both direct array and object with 'holidays' key
            if isinstance(data, dict) and 'holidays' in data:
                holidays_data = data['holidays']
            elif isinstance(data, list):
                holidays_data = data
            else:
                raise ValueError("Holidays data must be a list or an object with 'holidays' key")
            
            logger.info(f"Found {len(holidays_data)} holidays to import")
            
            # Import each holiday
            imported_count = 0
            skipped_count = 0
            
            for holiday in holidays_data:
                try:
                    self.create_holiday(holiday)
                    imported_count += 1
                except Exception as e:
                    logger.warning(f"Failed to import holiday {holiday.get('name', 'unknown')}: {e}")
                    skipped_count += 1
                    continue
            
            logger.info(f"Successfully imported {imported_count} holidays, skipped {skipped_count}")
            
            # Get final statistics
            stats_query = """
            MATCH (h:Holiday)
            RETURN count(DISTINCT h) AS total_holidays
            """
            stats = self.execute_cypher(stats_query)
            
            return {
                "success": True,
                "message": "Holidays loaded from JSON",
                "holidays_loaded": imported_count,
                "skipped": skipped_count,
                "total_holidays": stats[0]["total_holidays"] if stats else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to load holidays from JSON: {e}")
            raise
    
    def query_holidays(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query holidays with various filters.
        
        Args:
            filters: Dictionary with filter criteria
            
        Returns:
            List of matching holidays
        """
        logger.info(f"Querying holidays with filters: {filters}")
        
        # Build dynamic query
        match_clause = "MATCH (h:Holiday)"
        where_clauses = []
        params = {}
        
        # Add filters
        if filters.get("year"):
            where_clauses.append("h.year = $year")
            params["year"] = filters["year"]
        
        if filters.get("month"):
            where_clauses.append("h.month = $month")
            params["month"] = filters["month"]
        
        if filters.get("category"):
            where_clauses.append("h.category = $category")
            params["category"] = filters["category"]
        
        if filters.get("holiday_type"):
            where_clauses.append("h.holiday_type = $holiday_type")
            params["holiday_type"] = filters["holiday_type"]
        
        if filters.get("is_public_holiday") is not None:
            where_clauses.append("h.isPublicHoliday = $is_public_holiday")
            params["is_public_holiday"] = filters["is_public_holiday"]
        
        if filters.get("name"):
            where_clauses.append("toLower(h.name) CONTAINS toLower($name)")
            params["name"] = filters["name"]
        
        # Build WHERE clause
        where_clause = ""
        if where_clauses:
            where_clause = " WHERE " + " AND ".join(where_clauses)
        
        # Build RETURN clause
        return_clause = """
        RETURN h.id AS id,
               h.name AS name,
               h.description AS description,
               toString(h.start_date) AS start_date,
               toString(h.end_date) AS end_date,
               h.duration_days AS duration_days,
               h.holiday_type AS holiday_type,
               h.category AS category,
               h.isPublicHoliday AS is_public_holiday,
               h.year AS year,
               h.month AS month,
               h.day AS day,
               h.weekday AS weekday
        ORDER BY h.start_date
        """
        
        limit = filters.get("limit", 50)
        full_query = f"{match_clause}{where_clause} {return_clause} LIMIT {limit}"
        
        result = self.execute_query(full_query, params)
        logger.info(f"Found {len(result)} holidays")
        
        return result
    
    def get_by_year(self, year: int) -> List[Dict[str, Any]]:
        """Get all holidays for a specific year.
        
        Args:
            year: Year to query
            
        Returns:
            List of holidays in the year
        """
        return self.query_holidays({"year": year, "limit": 200})
    
    def get_by_category(self, category: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get holidays by category.
        
        Args:
            category: Holiday category
            year: Optional year filter
            
        Returns:
            List of holidays in the category
        """
        filters = {"category": category, "limit": 100}
        if year:
            filters["year"] = year
        return self.query_holidays(filters)
    
    def get_upcoming(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get upcoming holidays from today.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of upcoming holidays
        """
        logger.info(f"Getting upcoming {limit} holidays")
        
        cypher = """
        MATCH (h:Holiday)
        WHERE h.start_date >= date()
        RETURN h.id AS id,
               h.name AS name,
               h.description AS description,
               toString(h.start_date) AS start_date,
               h.holiday_type AS holiday_type,
               h.category AS category,
               h.isPublicHoliday AS is_public_holiday,
               h.year AS year,
               h.month AS month,
               h.day AS day,
               h.weekday AS weekday
        ORDER BY h.start_date
        LIMIT $limit
        """
        
        return self.execute_query(cypher, {"limit": limit})
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive holiday statistics.
        
        Returns:
            Statistics dictionary
        """
        logger.info("Getting holiday statistics")
        
        # Total count
        total = self.execute_query("MATCH (h:Holiday) RETURN count(h) AS total")
        
        # Count by year
        by_year = self.execute_query("""
            MATCH (h:Holiday)
            RETURN h.year AS year, count(h) AS count
            ORDER BY year
        """)
        
        # Count by category
        by_category = self.execute_query("""
            MATCH (h:Holiday)
            RETURN h.category AS category, count(h) AS count
            ORDER BY category
        """)
        
        # Public holidays count
        public = self.execute_query("""
            MATCH (h:Holiday {isPublicHoliday: true})
            RETURN count(h) AS count
        """)
        
        return {
            "total_holidays": total[0]["total"] if total else 0,
            "public_holidays": public[0]["count"] if public else 0,
            "by_year": by_year,
            "by_category": by_category
        }
