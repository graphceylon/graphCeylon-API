"""Base models for API request/response validation."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Application version")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class ProvenanceMetadata(BaseModel):
    """Provenance metadata for tracking data sources and operations."""
    source: Optional[str] = Field(None, description="Data source")
    timestamp: Optional[str] = Field(None, description="Operation timestamp")
    operation: Optional[str] = Field(None, description="Operation type")
    method: Optional[str] = Field(None, description="Method used")


class StatisticsResponse(BaseModel):
    """Response model for database statistics."""
    statistics: Dict[str, Any] = Field(..., description="Database statistics")
