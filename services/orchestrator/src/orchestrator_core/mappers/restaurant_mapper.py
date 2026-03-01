from pydantic import BaseModel
from typing import List, Optional
from ...api.schemas import ParsedIntent, OrchestrateRequest

class RestaurantSearchRequest(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None
    tags: List[str] = []
    limit: int = 10

def map_restaurant_request(pi: ParsedIntent, req: OrchestrateRequest) -> RestaurantSearchRequest:
    ents = pi.entities
    # entities is pydantic Entities
    city = getattr(ents, "city", None)
    country = getattr(ents, "country", None)
    tags = getattr(ents, "tags", None) or []

    # ensure vegan tag stays
    if "vegan" not in [t.lower() for t in tags]:
        # if user said vegan, it is already in tags in your example, but just in case:
        if "vegan" in (req.input_text or "").lower():
            tags.append("vegan")

    return RestaurantSearchRequest(
        city=city,
        country=country,
        tags=tags,
        limit=10,
    )