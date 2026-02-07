from typing import Any, Dict
from pathlib import Path
from services.recommender_service.src.itinerary.json_kg import query_attractions_from_json

def get_candidates_city(payload: Dict[str, Any], kg_path: Path, limit: int) -> Any:
    return query_attractions_from_json(
        payload,
        kg_path=kg_path,
        limit=limit,
        prefilter_limit=300,
    )
