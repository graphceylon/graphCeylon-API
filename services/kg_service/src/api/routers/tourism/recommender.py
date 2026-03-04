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

# ------------------------------------------------------------------
# Categories always excluded from route-based sub-attraction results.
# Add/remove entries here to control what the recommender never returns.
# ------------------------------------------------------------------
REJECTED_POI_CATEGORIES: list[str] = [
    "Shopping & City",
    "Food & Markets",
]

# ------------------------------------------------------------------
# Categories for shopping and dining recommendations.
# Used for the shopping-and-dining-on-route endpoint.
# ------------------------------------------------------------------
SHOPPING_DINING_CATEGORIES: list[str] = [
    "Shopping & City",
    "Food & Markets",
]


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
    
    Certain non-tourism categories (Shopping & City, Food & Markets) are
    automatically excluded to focus on tourist attractions.

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
    return service.find_attractions_on_route(request, rejected_categories=REJECTED_POI_CATEGORIES)


@router.post(
    "/call/shopping-and-dining-on-route",
    response_model=AttractionsOnRouteResponse,
    response_model_exclude_none=True,
)
def shopping_and_dining_on_route(
    request: AttractionsOnRouteRequest,
    driver=Depends(get_driver),
):
    """
    Discover shopping and dining spots along a sampled route.

    For each coordinate in **sampled_route_points** (processed in order),
    the endpoint searches for SubAttraction nodes within **corridor_km**
    kilometres that belong to shopping or food categories. Results are
    de-duplicated (each POI appears only once, tagged with the nearest
    waypoint index and minimum distance).
    
    Only returns sub-attractions categorized as "Shopping & City" or
    "Food & Markets" to help travelers find places to shop and eat
    along their route.

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
    return service.find_attractions_on_route(request, preferred_categories=SHOPPING_DINING_CATEGORIES)
