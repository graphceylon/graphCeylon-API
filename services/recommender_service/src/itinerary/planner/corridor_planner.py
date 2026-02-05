from typing import Any, Dict
from services.recommender_service.src.itinerary.ranking.corridor import query_attractions_along_route

def get_candidates_corridor(payload: Dict[str, Any], origin_city: str, dest_city: str, limit: int) -> Any:
    return query_attractions_along_route(
        origin_city=origin_city,
        destination_city=dest_city,
        payload=payload,
        limit=limit,
    )
