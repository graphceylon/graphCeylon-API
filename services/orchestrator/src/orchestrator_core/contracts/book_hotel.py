from pydantic import BaseModel
from typing import Optional, Dict, Any


class BookHotelRequest(BaseModel):
    city: str
    arrival: str
    departure: str
    adults: int = 2
    hotel_id: Optional[str] = None
    room_type: Optional[str] = None
    trace: Optional[Dict[str, Any]] = None


class BookHotelResponse(BaseModel):
    ok: bool = True
    status: str
    booking_id: Optional[str] = None
    message: Optional[str] = None