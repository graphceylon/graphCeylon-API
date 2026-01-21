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
]
