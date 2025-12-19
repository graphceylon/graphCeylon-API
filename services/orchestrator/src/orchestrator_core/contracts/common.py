#src/orchestrator_core/contracts/common.py
from typing import Optional
from pydantic import BaseModel


class BaseServiceRequest(BaseModel):
    intent: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    raw_text: str


class BaseLocationTimeRequest(BaseServiceRequest):
    city: Optional[str] = None
    country: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    time_of_day: Optional[str] = None
