"""
Hotel and Accommodation Data Models

Pydantic models for hotel ingestion from Google Hotels data
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

# Import common geolocation model
from models.common import CoordinatesModel as GPSCoordinates


class TransportType(str, Enum):
    """Transportation modes"""
    TAXI = "taxi"
    PUBLIC_TRANSPORT = "public_transport"
    WALKING = "walking"
    TRAIN = "train"
    BUS = "bus"
    

class HotelType(str, Enum):
    """Hotel accommodation types"""
    HOTEL = "hotel"
    RESORT = "resort"
    HOSTEL = "hostel"
    GUESTHOUSE = "guesthouse"
    HOMESTAY = "homestay"
    BOUTIQUE = "boutique"
    APARTMENT = "apartment"


class PriceTier(str, Enum):
    """Price categorization"""
    BUDGET = "budget"           # < $50/night
    MID_RANGE = "mid_range"     # $50-$150/night
    LUXURY = "luxury"           # $150-$300/night
    PREMIUM = "premium"         # > $300/night


class ProximityLevel(str, Enum):
    """Distance categories"""
    VERY_CLOSE = "very_close"   # < 2 km
    CLOSE = "close"             # 2-5 km
    MODERATE = "moderate"       # 5-10 km
    FAR = "far"                 # 10-20 km
    VERY_FAR = "very_far"       # > 20 km


# ========== Nested Models ==========

class TransportationOption(BaseModel):
    """Transportation details to nearby places"""
    type: str = Field(..., description="Transport mode (Taxi, Public transport, etc.)")
    duration: str = Field(..., description="Travel duration (e.g., '12 min', '1 hr 29 min')")
    duration_minutes: Optional[int] = Field(None, description="Duration in minutes (calculated)")
    cost_estimate: Optional[float] = Field(None, description="Estimated cost in USD")
    
    @validator('duration_minutes', pre=True, always=True)
    def calculate_duration_minutes(cls, v, values):
        """Parse duration string to minutes"""
        if v:
            return v
        
        duration_str = values.get('duration', '')
        if not duration_str:
            return None
            
        # Parse "12 min" or "1 hr 29 min" format
        total_minutes = 0
        parts = duration_str.lower().split()
        
        i = 0
        while i < len(parts):
            if i + 1 < len(parts):
                try:
                    value = int(parts[i])
                    unit = parts[i + 1]
                    
                    if 'hr' in unit or 'hour' in unit:
                        total_minutes += value * 60
                    elif 'min' in unit:
                        total_minutes += value
                    
                    i += 2
                except (ValueError, IndexError):
                    i += 1
            else:
                i += 1
        
        return total_minutes if total_minutes > 0 else None


class NearbyPlace(BaseModel):
    """Nearby point of interest"""
    category: str = Field(..., description="POI category (Point of interest, Temple, etc.)")
    name: str = Field(..., description="POI name")
    link: Optional[str] = Field(None, description="Google search link")
    thumbnail: Optional[str] = Field(None, description="Image thumbnail URL")
    rating: Optional[float] = Field(None, ge=0, le=5, description="Google rating")
    reviews: Optional[int] = Field(None, ge=0, description="Number of reviews")
    description: Optional[str] = Field(None, description="POI description")
    gps_coordinates: Optional[GPSCoordinates] = None
    transportations: List[TransportationOption] = Field(default_factory=list)


class HotelAmenity(BaseModel):
    """Hotel amenity/feature"""
    name: str = Field(..., description="Amenity name (wifi, pool, etc.)")
    category: Optional[str] = Field(None, description="Category (connectivity, recreation, dining)")
    available: bool = Field(True, description="Whether amenity is available")
    additional_charge: bool = Field(False, description="Whether extra charge applies")


# ========== Main Models ==========

class HotelBase(BaseModel):
    """Base hotel information"""
    name: str = Field(..., min_length=1, max_length=500, description="Hotel name")
    type: HotelType = Field(default=HotelType.HOTEL, description="Hotel type")
    description: Optional[str] = Field(None, description="Hotel description")
    link: Optional[str] = Field(None, description="Hotel website URL")
    
    # Location
    gps_coordinates: GPSCoordinates
    
    # Administrative location (to be enriched)
    province: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    
    # Pricing
    rate_per_night: Optional[float] = Field(None, ge=0, description="Rate per night in USD")
    total_rate: Optional[float] = Field(None, ge=0, description="Total rate for stay")
    currency: str = Field(default="USD", description="Currency code")
    price_tier: Optional[PriceTier] = None
    
    # Check-in/out
    check_in_time: Optional[str] = Field(None, description="Check-in time (e.g., '2:00 PM')")
    check_out_time: Optional[str] = Field(None, description="Check-out time")
    
    # Ratings
    rating: Optional[float] = Field(None, ge=0, le=5, description="Hotel rating (0-5)")
    reviews_count: Optional[int] = Field(None, ge=0, description="Number of reviews")
    
    # External IDs
    property_token: Optional[str] = Field(None, description="Google property token")
    place_id: Optional[str] = Field(None, description="Google Place ID")
    serpapi_link: Optional[str] = Field(None, description="SerpAPI details link")
    
    # Additional data
    images: List[str] = Field(default_factory=list, description="Image URLs")
    amenities: List[str] = Field(default_factory=list, description="List of amenities")
    nearby_places: List[NearbyPlace] = Field(default_factory=list)
    
    # Certifications
    eco_certified: bool = Field(default=False, description="Eco-certification status")
    
    @validator('price_tier', pre=True, always=True)
    def determine_price_tier(cls, v, values):
        """Auto-determine price tier from rate_per_night"""
        if v:
            return v
        
        rate = values.get('rate_per_night')
        if rate is None:
            return None
        
        if rate < 50:
            return PriceTier.BUDGET
        elif rate < 150:
            return PriceTier.MID_RANGE
        elif rate < 300:
            return PriceTier.LUXURY
        else:
            return PriceTier.PREMIUM


class HotelCreate(HotelBase):
    """Schema for creating a hotel"""
    attraction_name: str = Field(..., description="Associated attraction name")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Heritage Hotel Anuradhapura",
                "type": "hotel",
                "description": "Surrounded by trees and overlooking Tissa Wewa reservoir...",
                "link": "http://www.heritagehotel.lk/",
                "gps_coordinates": {
                    "latitude": 8.327515199999999,
                    "longitude": 80.3793055
                },
                "rate_per_night": 85.0,
                "total_rate": 170.0,
                "check_in_time": "2:00 PM",
                "check_out_time": "12:00 PM",
                "rating": 4.5,
                "reviews_count": 1234,
                "property_token": "ChcIlamulsbkkqclGgsvZy8xdGd3M2c1bRAB",
                "attraction_name": "Anuradhapura",
                "amenities": ["wifi", "pool", "restaurant"],
                "eco_certified": False
            }
        }


class HotelInDB(HotelBase):
    """Hotel as stored in database"""
    hotel_id: str = Field(..., description="Unique hotel identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Enriched fields
    distance_to_attraction_km: Optional[float] = Field(None, description="Distance to main attraction")
    proximity_level: Optional[ProximityLevel] = None
    
    class Config:
        from_attributes = True


class HotelResponse(HotelInDB):
    """Hotel response model for API"""
    nearby_attractions: List[str] = Field(default_factory=list, description="List of nearby attraction names")


# ========== Relationship Models ==========

class HotelAttractionRelationship(BaseModel):
    """Relationship between hotel and attraction"""
    hotel_id: str
    attraction_id: str
    attraction_name: str
    
    # Spatial
    distance_km: float = Field(..., ge=0, description="Distance in kilometers")
    proximity_level: ProximityLevel
    
    # Accessibility
    travel_time_taxi: Optional[int] = Field(None, description="Travel time by taxi (minutes)")
    travel_time_public: Optional[int] = Field(None, description="Travel time by public transport")
    travel_cost_taxi: Optional[float] = Field(None, description="Taxi cost estimate")
    
    # Confidence
    confidence: float = Field(default=1.0, ge=0, le=1, description="Relationship confidence score")
    source: str = Field(default="google_hotels", description="Data source")
    
    class Config:
        json_schema_extra = {
            "example": {
                "hotel_id": "hotel_heritage_anuradhapura",
                "attraction_id": "attraction_anuradhapura",
                "attraction_name": "Anuradhapura",
                "distance_km": 2.5,
                "proximity_level": "close",
                "travel_time_taxi": 12,
                "travel_time_public": 89,
                "travel_cost_taxi": 5.0,
                "confidence": 1.0
            }
        }


class HotelPOIRelationship(BaseModel):
    """Relationship between hotel and point of interest"""
    hotel_id: str
    poi_name: str
    poi_category: str
    
    distance_km: Optional[float] = None
    travel_time: Optional[int] = Field(None, description="Travel time in minutes")
    transport_type: Optional[TransportType] = None
    
    rating: Optional[float] = None
    reviews: Optional[int] = None


# ========== Ingestion Models ==========

class HotelIngestionBatch(BaseModel):
    """Batch of hotels for ingestion"""
    attraction_name: str = Field(..., description="Source attraction")
    attraction_description: Optional[str] = None
    attraction_geolocation: Optional[Dict[str, Any]] = None
    hotel_count: int = Field(..., ge=0)
    hotels: List[HotelCreate]
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Scraping metadata (timestamp, source, etc.)"
    )


class HotelIngestionResult(BaseModel):
    """Result of hotel ingestion operation"""
    success: bool
    hotels_created: int = 0
    relationships_created: int = 0
    pois_created: int = 0
    amenities_created: int = 0
    
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    processing_time_seconds: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HotelSearchQuery(BaseModel):
    """Search query for hotels"""
    attraction_name: Optional[str] = Field(None, description="Near specific attraction")
    province: Optional[str] = None
    district: Optional[str] = None
    
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = None
    price_tier: Optional[PriceTier] = None
    
    min_rating: Optional[float] = Field(None, ge=0, le=5)
    
    amenities: List[str] = Field(default_factory=list, description="Required amenities")
    
    max_distance_km: Optional[float] = Field(None, ge=0, description="Max distance from attraction")
    
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class HotelRecommendationQuery(BaseModel):
    """Query for hotel recommendations"""
    attractions: List[str] = Field(..., min_items=1, description="Attractions to visit")
    
    budget_per_night: Optional[float] = Field(None, ge=0)
    num_nights: int = Field(default=1, ge=1)
    
    preferred_amenities: List[str] = Field(default_factory=list)
    
    optimize_for: str = Field(
        default="distance",
        description="Optimization criteria: distance, price, rating, or balanced"
    )
    
    max_results: int = Field(default=5, ge=1, le=20)


# ========== Statistics Models ==========

class HotelStatistics(BaseModel):
    """Hotel dataset statistics"""
    total_hotels: int
    total_attractions_covered: int
    
    by_price_tier: Dict[str, int] = Field(default_factory=dict)
    by_province: Dict[str, int] = Field(default_factory=dict)
    by_rating: Dict[str, int] = Field(default_factory=dict)  # 1-star, 2-star, etc.
    
    average_price: float
    average_rating: float
    
    total_nearby_pois: int
    total_amenities: int
    
    coverage_map: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Attraction -> [Hotel IDs] mapping"
    )
