"""Models for tourism news data and operations."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# Request Models

class CreateNewsRequest(BaseModel):
    """Request model for creating a news article."""
    title: str = Field(..., description="Article title")
    date: Optional[str] = Field(None, description="Publication date (YYYY-MM-DD)")
    image_url: Optional[str] = Field(None, description="Article image URL")
    content: Optional[str] = Field(None, description="Article content/summary")
    read_more_url: Optional[str] = Field(None, description="Full article URL")
    category: Optional[str] = Field(None, description="News category")
    tags: Optional[List[str]] = Field(default_factory=list, description="Article tags")


class NewsQueryRequest(BaseModel):
    """Request model for querying news articles."""
    title: Optional[str] = Field(None, description="Search by article title")
    category: Optional[str] = Field(None, description="Filter by category")
    date_from: Optional[str] = Field(None, description="Filter articles from this date (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Filter articles to this date (YYYY-MM-DD)")
    year: Optional[int] = Field(None, description="Filter by year")
    month: Optional[int] = Field(None, ge=1, le=12, description="Filter by month (1-12)")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of results")


# Response Models

class NewsResponse(BaseModel):
    """Response model for news queries."""
    articles: List[Dict[str, Any]] = Field(..., description="List of news articles")
    count: int = Field(..., description="Number of articles returned")
    query_info: Optional[Dict[str, Any]] = Field(None, description="Query metadata")
