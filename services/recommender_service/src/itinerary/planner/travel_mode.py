from dataclasses import dataclass
from typing import Optional, Literal, List

OriginConfidence = Literal["explicit", "assumed", "unknown"]
ModeType = Literal["city", "corridor"]

@dataclass
class TravelMode:
    type: ModeType
    origin_city: Optional[str]
    destination_city: str
    include_stops: bool
    origin_confidence: OriginConfidence
    assumptions: List[str]
