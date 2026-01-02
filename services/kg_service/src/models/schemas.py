"""
DEPRECATED: This file is maintained for backward compatibility only.

This file re-exports models from the organized submodules for backward compatibility.

New code should import directly from:
- models.base: Core response and base models
- models.graph: Knowledge graph and temporal models
- models.domain: Domain-specific models (attractions, holidays, projects, news)
- models.ai: AI-related models (agent, graphrag)
"""

# Base models
from .base import (
    HealthResponse,
    ErrorResponse,
    StatisticsResponse,
)

# Knowledge Graph models (from graph submodule)
from .graph.knowledge_graph import (
    QueryRequest,
    QueryResponse,
    ReasonRequest,
    ReasonResponse,
    PredictRequest,
    PredictResponse,
    ConstraintReasonRequest,
    ConstraintReasonResponse,
    WriteRequest,
    WriteResponse,
    ValidationResponse,
    ExportResponse,
    ExplainResponse,
)

# Attraction models (from domain submodule)
from .domain.attraction import (
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

# Holiday models (from domain submodule)
from .domain.holiday import (
    HolidayModel,
    CreateHolidayRequest,
    HolidayQueryRequest,
    HolidayResponse,
    TemporalStructureResponse,
)

# Project models (from domain submodule)
from .domain.project import (
    TourismProjectModel,
    CreateProjectRequest,
    ProjectQueryRequest,
    ProjectResponse,
)

# News models (from domain submodule)
from .domain.news import (
    NewsArticleModel,
    CreateNewsRequest,
    NewsQueryRequest,
    NewsResponse,
)

# Railway models (from domain submodule)
from .domain.railway import (
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

# Legacy support - all models are now available through this module
__all__ = [
    # Base
    "HealthResponse",
    "ErrorResponse",
    "StatisticsResponse",
    "QueryRequest",
    "QueryResponse",
    "WriteRequest",
    "WriteResponse",
    # Reasoning
    "ReasonRequest",
    "ReasonResponse",
    "PredictRequest",
    "PredictResponse",
    "ConstraintReasonRequest",
    "ConstraintReasonResponse",
    "ValidationResponse",
    "ExportResponse",
    "ExplainResponse",
    # Attractions
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
    # Holidays
    "HolidayModel",
    "CreateHolidayRequest",
    "HolidayQueryRequest",
    "HolidayResponse",
    "TemporalStructureResponse",
    # Projects
    "TourismProjectModel",
    "CreateProjectRequest",
    "ProjectQueryRequest",
    "ProjectResponse",
    # News
    "NewsArticleModel",
    "CreateNewsRequest",
    "NewsQueryRequest",
    "NewsResponse",
    # Railway
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
]
