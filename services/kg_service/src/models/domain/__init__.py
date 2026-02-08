"""Domain models submodule for domain-specific entities."""

from .attraction import (
    LinkModel,
    CreateAttractionRequest,
    AttractionQueryRequest,
    AttractionResponse,
    AttractionSearchRequest,
    AttractionItem,
    AttractionSearchResponse,
)

from .holiday import (
    CreateHolidayRequest,
    HolidayQueryRequest,
    HolidayResponse,
    TemporalStructureResponse,
)

from .project import (
    TourismProjectModel,
    CreateProjectRequest,
    ProjectQueryRequest,
    ProjectResponse,
)

from .news import (
    CreateNewsRequest,
    NewsQueryRequest,
    NewsResponse,
)

from .railway import (
    TrainType,
    RailwayStation,
    TrainSchedule,
    RailwayStationQueryRequest,
    RailwayStationResponse,
    TrainScheduleQueryRequest,
    TrainScheduleResponse,
    RouteQueryRequest,
    RouteResponse,
    CreateRailwayStationRequest,
    CreateTrainScheduleRequest,
    StationStatistics,
    ScheduleStatistics,
    TransportSearchRequest,
    TransportOption,
    TransportSearchResponse,
)

from .hotel import (
    HotelCreate,
    HotelSearchQuery,
    HotelRecommendationQuery,
    HotelStatistics,
    AccommodationSearchRequest,
    HotelItemResponse,
    OrchestratorSearchResponse,
)

__all__ = [
    # Attraction models
    "LinkModel",
    "CreateAttractionRequest",
    "AttractionQueryRequest",
    "AttractionResponse",
    "AttractionSearchRequest",
    "AttractionItem",
    "AttractionSearchResponse",
    # Holiday models
    "CreateHolidayRequest",
    "HolidayQueryRequest",
    "HolidayResponse",
    "TemporalStructureResponse",
    # Project models
    "TourismProjectModel",
    "CreateProjectRequest",
    "ProjectQueryRequest",
    "ProjectResponse",
    # News models
    "CreateNewsRequest",
    "NewsQueryRequest",
    "NewsResponse",
    # Railway & Transport models
    "TrainType",
    "RailwayStation",
    "TrainSchedule",
    "RailwayStationQueryRequest",
    "RailwayStationResponse",
    "TrainScheduleQueryRequest",
    "TrainScheduleResponse",
    "RouteQueryRequest",
    "RouteResponse",
    "CreateRailwayStationRequest",
    "CreateTrainScheduleRequest",
    "StationStatistics",
    "ScheduleStatistics",
    "TransportSearchRequest",
    "TransportOption",
    "TransportSearchResponse",
    # Hotel & Accommodation models
    "HotelCreate",
    "HotelSearchQuery",
    "HotelRecommendationQuery",
    "HotelStatistics",
    "AccommodationSearchRequest",
    "HotelItemResponse",
    "OrchestratorSearchResponse",
]
