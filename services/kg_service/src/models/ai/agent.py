"""Models for agent interface operations."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AgentSearchRequest(BaseModel):
    """Request model for agent semantic search."""
    query: str = Field(..., description="Natural language query")
    limit: int = Field(5, ge=1, le=20, description="Maximum number of results")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional search filters")


class AgentPlanRequest(BaseModel):
    """Request model for agent planning operations."""
    intent: str = Field(..., description="User intent description")
    waypoints: List[str] = Field(..., description="List of waypoint names")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Optional constraints")
