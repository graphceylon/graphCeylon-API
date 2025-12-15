"""Models for agent interface operations."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# Request Models

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


# Response Models

class AgentSearchResponse(BaseModel):
    """Response model for agent search operations."""
    result: List[Dict[str, Any]] = Field(..., description="Search results")
    explanation: Dict[str, Any] = Field(..., description="Search explanation")


class AgentPlanResponse(BaseModel):
    """Response model for agent planning operations."""
    result: Dict[str, Any] = Field(..., description="Planning result")
    explanation: List[Dict[str, Any]] = Field(..., description="Plan explanation")
    feasible: bool = Field(..., description="Whether the plan is feasible")


class AgentExplainResponse(BaseModel):
    """Response model for agent explanation operations."""
    entity: Dict[str, Any] = Field(..., description="Entity information")
    context: List[Dict[str, Any]] = Field(..., description="Related context")
    provenance: str = Field(..., description="Data provenance information")
