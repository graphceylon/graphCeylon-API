"""Holiday and Temporal domain API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
import logging

from database.manager import DatabaseManager
from models.domain.holiday import (
    HolidayQueryRequest, HolidayResponse, CreateHolidayRequest,
    TemporalStructureResponse
)
from api.dependencies import get_db_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/holidays", tags=["Holidays & Temporal"])


@router.post("/initialize-temporal", response_model=Dict[str, Any])
async def initialize_temporal_structure(db: DatabaseManager = Depends(get_db_manager)):
    """
    Initialize the temporal structure (Year -> Month hierarchy).
    
    This creates:
    - Year nodes (2024, 2025, 2026)
    - Month nodes for each year
    - Relationships to Temporal domain
    - Indexes for performance
    """
    try:
        result = db.initialize_temporal_structure()
        return result
    except Exception as e:
        logger.error(f"Failed to initialize temporal structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load", response_model=Dict[str, Any])
async def load_holidays_from_json(db: DatabaseManager = Depends(get_db_manager)):
    """
    Load holidays from JSON file and connect to temporal structure.
    
    This:
    - Loads holidays from holidays.json
    - Creates Holiday nodes
    - Links holidays to Years and Months
    - Creates holiday categories and types
    - Links to Temporal domain
    """
    try:
        result = db.load_holidays_from_json()
        return result
    except Exception as e:
        logger.error(f"Failed to load holidays: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=HolidayResponse)
async def query_holidays(
    request: HolidayQueryRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Query holidays with various filters.
    
    Filters:
    - year: Filter by specific year
    - month: Filter by month (1-12)
    - category: Filter by category (Religious, Cultural, National, General)
    - holiday_type: Filter by type (Poya Day, Public Holiday, etc.)
    - is_public_holiday: Filter public holidays only
    - name: Search by holiday name (case-insensitive)
    - limit: Maximum number of results
    """
    try:
        filters = request.dict(exclude_none=True)
        holidays = db.query_holidays(filters)
        
        return HolidayResponse(
            holidays=holidays,
            count=len(holidays),
            query_info={
                "filters_applied": {k: v for k, v in filters.items() if k != "limit"},
                "limit": filters.get("limit", 50)
            }
        )
    except Exception as e:
        logger.error(f"Failed to query holidays: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/year/{year}", response_model=HolidayResponse)
async def get_holidays_by_year(
    year: int,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get all holidays for a specific year."""
    try:
        holidays = db.get_holidays_by_year(year)
        return HolidayResponse(
            holidays=holidays,
            count=len(holidays),
            query_info={"year": year}
        )
    except Exception as e:
        logger.error(f"Failed to get holidays by year: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/year/{year}/month/{month}", response_model=HolidayResponse)
async def get_holidays_by_month(
    year: int,
    month: int,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get all holidays for a specific year and month."""
    try:
        if month < 1 or month > 12:
            raise HTTPException(status_code=400, detail="Month must be between 1 and 12")
        
        holidays = db.get_holidays_by_year_month(year, month)
        return HolidayResponse(
            holidays=holidays,
            count=len(holidays),
            query_info={"year": year, "month": month}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get holidays by month: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/category/{category}", response_model=HolidayResponse)
async def get_holidays_by_category(
    category: str,
    year: Optional[int] = None,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Get holidays by category (Religious, Cultural, National, General).
    
    Optional year parameter to filter by specific year.
    """
    try:
        holidays = db.get_holidays_by_category(category, year)
        return HolidayResponse(
            holidays=holidays,
            count=len(holidays),
            query_info={"category": category, "year": year}
        )
    except Exception as e:
        logger.error(f"Failed to get holidays by category: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/type/{holiday_type}", response_model=HolidayResponse)
async def get_holidays_by_type(
    holiday_type: str,
    year: Optional[int] = None,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Get holidays by type (Poya Day, Public Holiday, National Holiday, etc.).
    
    Optional year parameter to filter by specific year.
    """
    try:
        holidays = db.get_holidays_by_type(holiday_type, year)
        return HolidayResponse(
            holidays=holidays,
            count=len(holidays),
            query_info={"holiday_type": holiday_type, "year": year}
        )
    except Exception as e:
        logger.error(f"Failed to get holidays by type: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/public", response_model=HolidayResponse)
async def get_public_holidays(
    year: Optional[int] = None,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Get all public holidays.
    
    Optional year parameter to filter by specific year.
    """
    try:
        holidays = db.get_public_holidays(year)
        return HolidayResponse(
            holidays=holidays,
            count=len(holidays),
            query_info={"is_public_holiday": True, "year": year}
        )
    except Exception as e:
        logger.error(f"Failed to get public holidays: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temporal-structure", response_model=TemporalStructureResponse)
async def get_temporal_structure(db: DatabaseManager = Depends(get_db_manager)):
    """
    Get the complete temporal structure.
    
    Returns:
    - Domain information
    - Years with month counts
    - Holiday counts per year/month
    """
    try:
        structure = db.get_temporal_structure()
        return TemporalStructureResponse(
            structure=structure.get("structure", {}),
            summary=structure.get("summary", {})
        )
    except Exception as e:
        logger.error(f"Failed to get temporal structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=Dict[str, Any])
async def get_holiday_statistics(db: DatabaseManager = Depends(get_db_manager)):
    """
    Get holiday statistics.
    
    Returns:
    - Total holidays count
    - Count by year
    - Count by category
    - Count by type
    - Count by month
    """
    try:
        stats = db.get_holiday_statistics()
        return stats
    except Exception as e:
        logger.error(f"Failed to get holiday statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create", response_model=Dict[str, Any])
async def create_holiday(
    request: CreateHolidayRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Create a new holiday.
    
    Note: The holiday will be automatically linked to the appropriate Year and Month
    based on the start_date.
    """
    try:
        result = db.create_holiday(request.dict())
        return result
    except Exception as e:
        logger.error(f"Failed to create holiday: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upcoming", response_model=HolidayResponse)
async def get_upcoming_holidays(
    limit: int = 10,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Get upcoming holidays from today.
    
    Returns holidays sorted by date, starting from today.
    """
    try:
        holidays = db.get_upcoming_holidays(limit)
        return HolidayResponse(
            holidays=holidays,
            count=len(holidays),
            query_info={"type": "upcoming", "limit": limit}
        )
    except Exception as e:
        logger.error(f"Failed to get upcoming holidays: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=HolidayResponse)
async def search_holidays(
    query: str,
    limit: int = 20,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Search holidays by name or description.
    
    Case-insensitive search across holiday names and descriptions.
    """
    try:
        holidays = db.search_holidays(query, limit)
        return HolidayResponse(
            holidays=holidays,
            count=len(holidays),
            query_info={"search_query": query, "limit": limit}
        )
    except Exception as e:
        logger.error(f"Failed to search holidays: {e}")
        raise HTTPException(status_code=500, detail=str(e))
