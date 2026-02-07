"""Domain models submodule for domain-specific entities."""

from .attraction import (
    CoordinatesModel,
    MapLinksModel,
    AdministrativeAreasModel,
    AddressInfoModel,
    GeocodingMetadataModel,
    GeolocationModel,
    LinkModel,
    GooglePlaceDataModel,
    AttractionModel,
    CreateAttractionRequest,
    AttractionQueryRequest,
    AttractionResponse,
)

from .holiday import (
    HolidayModel,
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
    NewsArticleModel,
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
)

from .hotel import (
    HotelType,
    HotelBase,
    HotelCreate,
    HotelSearchQuery,
    HotelRecommendationQuery,
    HotelStatistics,
)

from .orchestrator import (
    AccommodationSearchRequest,
    HotelItemResponse,
    OrchestratorSearchResponse,
)

from .attraction_orchestrator import (
    AttractionSearchRequest,
    AttractionItem,
    AttractionSearchResponse,
)

from .transport_orchestrator import (
    TransportSearchRequest,
    TransportOption,
    TransportSearchResponse,
)

__all__ = [
    # Attraction models
    "CoordinatesModel",
    "MapLinksModel",
    "AdministrativeAreasModel",
    "AddressInfoModel",
    "GeocodingMetadataModel",
    "GeolocationModel",
    "LinkModel",
    "GooglePlaceDataModel",
    "AttractionModel",
    "CreateAttractionRequest",
    "AttractionQueryRequest",
    "AttractionResponse",
    # Holiday models
    "HolidayModel",
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
    "NewsArticleModel",
    "CreateNewsRequest",
    "NewsQueryRequest",
    "NewsResponse",
    # Railway models
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
    # Hotel models
    "HotelType",
    "HotelBase",
    "HotelCreate",
    "HotelSearchQuery",
    "HotelRecommendationQuery",
    "HotelStatistics",
    # Orchestrator models
    "AccommodationSearchRequest",
    "HotelItemResponse",
    "OrchestratorSearchResponse",
    "AttractionSearchRequest",
    "AttractionItem",
    "AttractionSearchResponse",
    "TransportSearchRequest",
    "TransportOption",
    "TransportSearchResponse",
]
