"""
Attraction Orchestrator Models

Data models for attraction search functionality used by orchestrator service
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class AttractionSearchRequest(BaseModel):
    """Request model for attraction search"""
    
    city: str = Field(..., description="City name (e.g., 'Kandy', 'Colombo', 'Galle')")
    country: str = Field(..., description="Country name (e.g., 'Sri Lanka')")
    poi_name: Optional[str] = Field(None, description="Specific POI name to search for")
    poi_category: Optional[str] = Field(None, description="Category of POI (e.g., 'temple', 'museum', 'park')")
    days: Optional[int] = Field(None, description="Number of days for trip planning context")
    tags: Optional[List[str]] = Field(None, description="Tags for filtering (e.g., ['historical', 'cultural'])")
    user_id: Optional[str] = Field(None, description="User ID for personalization")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    query: Optional[str] = Field(None, description="Natural language query")
    
    class Config:
        json_schema_extra = {
            "example": {
                "city": "Kandy",
                "country": "Sri Lanka",
                "poi_name": None,
                "poi_category": "temple",
                "days": 2,
                "tags": ["cultural", "historical"],
                "user_id": "user123",
                "session_id": "session456",
                "query": "What are the main tourist attractions in Kandy?"
            }
        }


class AttractionItem(BaseModel):
    """Single attraction in search results"""
    
    name: str = Field(..., description="Attraction name")
    category: Optional[str] = Field(None, description="Attraction category/type")
    description: Optional[str] = Field(None, description="Brief description")
    location: Optional[str] = Field(None, description="Location/address")
    open_hours: Optional[str] = Field(None, description="Opening hours")
    entry_fee_lkr: Optional[str] = Field(None, description="Entry fee in LKR")
    source: str = Field(default="kg_service", description="Data source")
    
    # Optional fields for additional details
    rating: Optional[float] = Field(None, description="Google rating (0-5)")
    coordinates: Optional[str] = Field(None, description="Lat, Lon coordinates")
    website: Optional[str] = Field(None, description="Official website")
    phone: Optional[str] = Field(None, description="Phone number")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Temple of the Sacred Tooth Relic",
                "category": "temple",
                "description": "Buddhist temple housing the relic of the tooth of Buddha",
                "location": "Sri Dalada Veediya, Kandy",
                "open_hours": "5:30 AM - 8:00 PM",
                "entry_fee_lkr": "1500",
                "source": "kg_service",
                "rating": 4.6,
                "coordinates": "7.2934, 80.6405",
                "website": "http://sridaladamaligawa.lk",
                "phone": "+94 81 223 4226"
            }
        }


class AttractionSearchResponse(BaseModel):
    """Response model for attraction search"""
    
    ok: bool = Field(..., description="Whether search was successful")
    city: str = Field(..., description="City searched")
    country: str = Field(..., description="Country searched")
    items: List[AttractionItem] = Field(default_factory=list, description="List of attractions")
    summary: str = Field(default="", description="Natural language summary of results")
    
    # Error handling
    error: Optional[str] = Field(None, description="Error type if ok=False")
    details: Optional[str] = Field(None, description="Error details if ok=False")
    
    class Config:
        json_schema_extra = {
            "example": {
                "ok": True,
                "city": "Kandy",
                "country": "Sri Lanka",
                "items": [
                    {
                        "name": "Temple of the Sacred Tooth Relic",
                        "category": "temple",
                        "description": "Buddhist temple housing the relic of the tooth of Buddha",
                        "location": "Sri Dalada Veediya, Kandy",
                        "open_hours": "5:30 AM - 8:00 PM",
                        "entry_fee_lkr": "1500",
                        "source": "kg_service"
                    }
                ],
                "summary": "Found 5 attractions in Kandy including temples, gardens, and cultural sites."
            }
        }
