"""
Orchestrator Service Models

Data models for orchestrator service communication
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AccommodationSearchRequest(BaseModel):
    """Request model for orchestrator hotel search"""
    intent: str = Field(..., description="Intent type (e.g., 'info_accommodation')")
    raw_text: str = Field(..., description="User's original query")
    user_id: str = Field(..., description="User UUID")
    session_id: str = Field(..., description="Session identifier")
    city: Optional[str] = Field(None, description="City name filter")
    country: Optional[str] = Field(None, description="Country filter (e.g., 'Sri Lanka')")
    min_star_rating: Optional[int] = Field(None, ge=0, le=5, description="Minimum star rating")
    max_star_rating: Optional[int] = Field(None, ge=0, le=5, description="Maximum star rating")
    must_have_amenities: List[str] = Field(
        default_factory=list,
        description="Required amenities (normalized: wifi, ac, pool, breakfast, parking, gym, spa, family_rooms)"
    )
    max_price_lkr: Optional[float] = Field(None, ge=0, description="Maximum price in LKR")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    trace: Optional[Dict[str, Any]] = Field(None, description="Trace metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "intent": "info_accommodation",
                "raw_text": "What are 3-star hotels in Colombo?",
                "user_id": "abfe4e3e-06d7-4081-815d-150d92f3070a",
                "session_id": "auto_test",
                "city": "Colombo",
                "country": "Sri Lanka",
                "min_star_rating": 3,
                "max_star_rating": 3,
                "must_have_amenities": ["wifi", "ac"],
                "max_price_lkr": 50000,
                "limit": 10,
                "trace": {
                    "domain_category": "hotel",
                    "preference_sources": {
                        "star_preference": "query",
                        "must_have_amenities": "db"
                    }
                }
            }
        }


class HotelItemResponse(BaseModel):
    """Individual hotel item in orchestrator response"""
    name: str
    city: Optional[str]
    country: str = "Sri Lanka"
    star_rating: Optional[int]
    price_range_lkr: Dict[str, float]
    amenities: List[str]
    address: Optional[str]
    geo: Dict[str, float]
    source: str = "neo4j"
    kg_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Hotel XYZ",
                "city": "Colombo",
                "country": "Sri Lanka",
                "star_rating": 3,
                "price_range_lkr": {
                    "min": 18000,
                    "max": 28000
                },
                "amenities": ["wifi", "ac", "breakfast"],
                "address": "Colombo 03",
                "geo": {
                    "lat": 6.9147,
                    "lon": 79.8636
                },
                "source": "neo4j",
                "kg_id": "Hotel:123"
            }
        }


class OrchestratorSearchResponse(BaseModel):
    """Response model for orchestrator hotel search"""
    ok: bool
    count: Optional[int] = None
    items: Optional[List[HotelItemResponse]] = None
    trace: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    details: Optional[str] = None

    model_config = {
        # Exclude null/None values from JSON response
        "json_schema_extra": {
            "success_example": {
                "ok": True,
                "count": 2,
                "items": [
                    {
                        "name": "Hotel XYZ",
                        "city": "Colombo",
                        "country": "Sri Lanka",
                        "star_rating": 3,
                        "price_range_lkr": {"min": 18000, "max": 28000},
                        "amenities": ["wifi", "ac", "breakfast"],
                        "address": "Colombo 03",
                        "geo": {"lat": 6.9147, "lon": 79.8636},
                        "source": "neo4j",
                        "kg_id": "Hotel:123"
                    }
                ],
                "trace": {
                    "cypher_ms": 12,
                    "filters_applied": {
                        "city": "Colombo",
                        "min_star_rating": 3,
                        "max_star_rating": 3,
                        "must_have_amenities": ["wifi", "ac"],
                        "max_price_lkr": 50000
                    }
                }
            },
            "no_results_example": {
                "ok": True,
                "count": 0,
                "items": [],
                "trace": {"reason": "No matches"}
            },
            "error_example": {
                "ok": False,
                "error": "Neo4j query failed",
                "details": "label Hotel not found"
            }
        }
    }
