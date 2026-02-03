# src/orchestrator_core/contracts/accommodation.py
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class AccommodationSearchRequest(BaseModel):
    intent: str
    raw_text: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    city: Optional[str] = None
    country: Optional[str] = None

    min_star_rating: Optional[int] = None
    max_star_rating: Optional[int] = None
    must_have_amenities: List[str] = []
    max_price_lkr: Optional[int] = None

    limit: int = 10

    # Optional: extra debug/trace metadata
    trace: Dict[str, Any] = {}


# -------------------------
# ✅ RESPONSE CONTRACTS
# -------------------------

class AccommodationItem(BaseModel):
    # Keep common fields you’ll almost always have:
    name: str
    city: Optional[str] = None
    country: Optional[str] = None

    # Optional ranking / scoring fields
    score: Optional[float] = None
    distance_km: Optional[float] = None

    # Pricing / rating
    price_lkr: Optional[float] = None
    star_rating: Optional[float] = None

    # Amenities + metadata
    amenities: List[str] = Field(default_factory=list)
    address: Optional[str] = None

    # Links/media (optional)
    url: Optional[str] = None
    image_url: Optional[str] = None

    # Debug / extra (don’t break if provider returns extra keys)
    meta: Dict[str, Any] = Field(default_factory=dict)


class AccommodationSearchResponse(BaseModel):
    ok: bool = True
    intent: Optional[str] = None
    query: Dict[str, Any] = Field(default_factory=dict)

    # Results
    items: List[AccommodationItem] = Field(default_factory=list)
    total: Optional[int] = None
    limit: Optional[int] = None

    # Helpful messages/errors
    message: Optional[str] = None
    error: Optional[str] = None

    # Trace/debug passthrough
    trace: Dict[str, Any] = Field(default_factory=dict)
