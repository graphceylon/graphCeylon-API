"""
Transport Orchestrator Models

Data models for orchestrator transport service communication
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TransportSearchRequest(BaseModel):
    """Request model for orchestrator transport search"""
    origin: str = Field(..., description="Starting location/city")
    destination: str = Field(..., description="Ending location/city")
    city: Optional[str] = Field(None, description="City context (optional)")
    country: str = Field(default="Sri Lanka", description="Country")
    time_of_day: Optional[str] = Field(None, description="Preferred time (morning/afternoon/evening)")
    days: Optional[List[str]] = Field(None, description="Specific days of week")
    budget_level: Optional[str] = Field(None, description="Budget constraint (low/medium/high)")
    preferred_transport: List[str] = Field(default_factory=list, description="Preferred transport modes")
    tags: List[str] = Field(default_factory=list, description="Additional tags/preferences")
    user_id: str = Field(..., description="User UUID")
    session_id: str = Field(..., description="Session identifier")
    query: str = Field(..., description="User's original query")

    class Config:
        json_schema_extra = {
            "example": {
                "origin": "Colombo",
                "destination": "Kandy",
                "city": None,
                "country": "Sri Lanka",
                "time_of_day": None,
                "days": None,
                "budget_level": None,
                "preferred_transport": [],
                "tags": [],
                "user_id": "abfe4e3e-06d7-4081-815d-150d92f3070a",
                "session_id": "auto_test",
                "query": "How can I travel from Colombo to Kandy?"
            }
        }


class TransportOption(BaseModel):
    """Individual transport option in response"""
    mode: str = Field(..., description="Transport mode (train/bus/car/etc)")
    summary: str = Field(..., description="Brief description of the route")
    estimated_time_min: int = Field(..., description="Estimated travel time in minutes")
    estimated_cost_lkr: float = Field(..., description="Estimated cost in LKR")
    tips: str = Field(..., description="Travel tips and recommendations")
    source: str = Field(..., description="Data source (e.g., 'Sri Lanka Railways')")

    class Config:
        json_schema_extra = {
            "example": {
                "mode": "train",
                "summary": "Colombo Fort to Kandy scenic train route",
                "estimated_time_min": 180,
                "estimated_cost_lkr": 300,
                "tips": "Reserve seats in advance",
                "source": "Sri Lanka Railways"
            }
        }


class TransportSearchResponse(BaseModel):
    """Response model for orchestrator transport search"""
    ok: bool
    origin: str
    destination: str
    country: str = "Sri Lanka"
    options: List[TransportOption] = Field(default_factory=list)
    summary: str = Field(..., description="Overall summary and recommendations")
    error: Optional[str] = None
    details: Optional[str] = None

    class Config:
        json_schema_extra = {
            "success_example": {
                "ok": True,
                "origin": "Colombo",
                "destination": "Kandy",
                "country": "Sri Lanka",
                "options": [
                    {
                        "mode": "train",
                        "summary": "Colombo Fort to Kandy scenic train route",
                        "estimated_time_min": 180,
                        "estimated_cost_lkr": 300,
                        "tips": "Reserve seats in advance",
                        "source": "Sri Lanka Railways"
                    },
                    {
                        "mode": "bus",
                        "summary": "A1 highway intercity bus",
                        "estimated_time_min": 210,
                        "estimated_cost_lkr": 450,
                        "tips": "AC buses available from Pettah",
                        "source": "SLTB"
                    }
                ],
                "summary": "Train is the most scenic option; bus is slightly faster during off-peak hours"
            },
            "error_example": {
                "ok": False,
                "origin": "Colombo",
                "destination": "Invalid City",
                "country": "Sri Lanka",
                "options": [],
                "summary": "",
                "error": "No routes found",
                "details": "Destination station not found in database"
            }
        }
