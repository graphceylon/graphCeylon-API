from typing import Any, Dict
from services.recommender_service.src.itinerary.ranking.corridor import query_attractions_along_route

def get_candidates_corridor(payload: Dict[str, Any], origin_city: str, dest_city: str, limit: int) -> Any:
    # 1) Call corridor query WITHOUT limit (because corridor.py doesn't accept it)
    base = query_attractions_along_route(
        payload=payload,
        origin_city=origin_city,
        destination_city=dest_city,
    )

    # 2) Apply limit AFTER getting candidates
    if hasattr(base, "candidates") and isinstance(base.candidates, list):
        base.candidates = base.candidates[: int(limit)]

    # 3) Optional debug
    if hasattr(base, "debug") and isinstance(base.debug, dict):
        base.debug["limit_applied"] = int(limit)

    return base
