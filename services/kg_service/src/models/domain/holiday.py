"""Models for holiday data and operations."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# Request Models

class CreateHolidayRequest(BaseModel):
    """Request model for creating a holiday."""
    name: str = Field(..., description="Holiday name")
    description: Optional[str] = Field(None, description="Holiday description")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    holiday_type: str = Field(..., description="Type of holiday")
    category: str = Field(..., description="Category (Religious, Cultural, National, General)")
    is_public_holiday: bool = Field(True, description="Whether it's a public holiday")
    location: Optional[str] = Field(None, description="Specific location if applicable")


class HolidayQueryRequest(BaseModel):
    """Request model for querying holidays."""
    year: Optional[int] = Field(None, description="Filter by year")
    month: Optional[int] = Field(None, ge=1, le=12, description="Filter by month (1-12)")
    category: Optional[str] = Field(None, description="Filter by category")
    holiday_type: Optional[str] = Field(None, description="Filter by holiday type")
    is_public_holiday: Optional[bool] = Field(None, description="Filter by public holiday status")
    name: Optional[str] = Field(None, description="Search by holiday name")
    limit: int = Field(50, ge=1, le=200, description="Maximum number of results")


# Response Models

class HolidayResponse(BaseModel):
    """Response model for holiday queries."""
    holidays: List[Dict[str, Any]] = Field(..., description="List of holidays")
    count: int = Field(..., description="Number of holidays returned")
    query_info: Optional[Dict[str, Any]] = Field(None, description="Query metadata")


class TemporalStructureResponse(BaseModel):
    """Response model for temporal structure queries."""
    structure: Dict[str, Any] = Field(..., description="Temporal structure data")
    summary: Optional[Dict[str, Any]] = Field(None, description="Summary statistics")
