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
