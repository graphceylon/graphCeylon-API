from pydantic import BaseModel
from typing import Optional, Dict, Any


class BookHotelRequest(BaseModel):
    city: Optional[str] = None
    arrival: Optional[str] = None
    departure: Optional[str] = None
    adults: int = 2
    room_category_id: Optional[int] = None   # ✅ add these
    room_type_id: Optional[int] = None        # ✅
    meal_plan_id: Optional[int] = None        # ✅
    rate_code_id: Optional[int] = None        # ✅
    property_id: Optional[int] = None         # ✅
    property_code: Optional[str] = None       # ✅
    trace: Optional[dict] = None


class BookHotelResponse(BaseModel):
    ok: bool = True
    status: str
    booking_id: Optional[str] = None
    message: Optional[str] = None