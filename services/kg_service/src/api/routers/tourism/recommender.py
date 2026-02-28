"""Recommender API endpoints.

Provides route-based attraction discovery — given a sequence of GPS
waypoints the client can discover sub-attractions that lie within a
configurable corridor along the route.
"""

import logging
from fastapi import APIRouter, Depends

from api.dependencies import get_driver
from models.domain.recommender import (
    AttractionsOnRouteRequest,
    AttractionsOnRouteResponse,
)
from services.recommender import RouteAttractionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/Recommender", tags=["recommender"])


@router.post(
    "/call/attractions-on-route",
    response_model=AttractionsOnRouteResponse,
    response_model_exclude_none=True,
)
def attractions_on_route(
    request: AttractionsOnRouteRequest,
    driver=Depends(get_driver),
):
    """
    Discover sub-attractions along a sampled route.

    For each coordinate in **sampled_route_points** (processed in order),
    the endpoint searches for SubAttraction nodes within **corridor_km**
    kilometres.  Results are de-duplicated (each POI appears only once,
    tagged with the nearest waypoint index and minimum distance).

    **Example Request:**
    ```json
    {
        "country": "Sri Lanka",
        "origin_city": "Colombo",
        "destination_city": "Galle",
        "corridor_km": 15.0,
        "limit": 80,
        "sampled_route_points": [
            [6.92708, 79.86119],
            [6.90738, 79.93196],
            [6.85343, 79.97830],
            [6.76399, 79.98675]
        ]
    }
    ```
    """
    service = RouteAttractionService(driver)
    return service.find_attractions_on_route(request)
