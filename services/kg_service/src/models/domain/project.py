"""Models for tourism project data and operations."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# Request Models

class TourismProjectModel(BaseModel):
    """Model for tourism project data."""
    title: str = Field(..., description="Project title")
    image: Optional[str] = Field(None, description="Project image URL")
    description: Optional[str] = Field(None, description="Project description")
    details: Optional[List[str]] = Field(default_factory=list, description="Project details")
    contact_text: Optional[str] = Field(None, description="Contact information")
    href: Optional[str] = Field(None, description="Project page link")


class CreateProjectRequest(BaseModel):
    """Request model for creating a tourism project."""
    title: str = Field(..., description="Project title")
    image: Optional[str] = Field(None, description="Project image URL")
    description: Optional[str] = Field(None, description="Project description")
    details: Optional[List[str]] = Field(default_factory=list, description="Project details")
    contact_text: Optional[str] = Field(None, description="Contact information")
    href: Optional[str] = Field(None, description="Project page link")
    province: Optional[str] = Field(None, description="Province name to link project to")
    district: Optional[str] = Field(None, description="District name to link project to")
    project_type: Optional[str] = Field(None, description="Type of project (Infrastructure, Regional, etc.)")


class ProjectQueryRequest(BaseModel):
    """Request model for querying tourism projects."""
    title: Optional[str] = Field(None, description="Search by project title")
    province: Optional[str] = Field(None, description="Filter by province")
    district: Optional[str] = Field(None, description="Filter by district")
    project_type: Optional[str] = Field(None, description="Filter by project type")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of results")


# Response Models

class ProjectResponse(BaseModel):
    """Response model for project queries."""
    projects: List[Dict[str, Any]] = Field(..., description="List of projects")
    count: int = Field(..., description="Number of projects returned")
    query_info: Optional[Dict[str, Any]] = Field(None, description="Query metadata")
