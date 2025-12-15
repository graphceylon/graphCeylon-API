#src/orchestrator_core/contracts/price.py
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from .common import BaseLocationTimeRequest


class PriceForecastRequest(BaseLocationTimeRequest):
    intent: str = "forecast_price"

    # price context (optional but useful)
    poi_name: Optional[str] = None              # e.g., "Ella"
    category: Optional[str] = None              # "hotel" | "food" | "transport" | "ticket" | etc.
    currency: Optional[str] = "LKR"             # default LKR if you want


class PriceForecastResponse(BaseModel):
    location: str
    category: str
    start_date: str
    end_date: str
    currency: str = "LKR"

    forecast_summary: str
    daily: List[Dict[str, Any]] = []            # [{date, price, ...}]
    confidence: Optional[float] = None
