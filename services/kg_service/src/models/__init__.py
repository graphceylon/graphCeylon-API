"""Models package for the Knowledge Graph application.

This package organizes models into logical submodules:
- base: Core response and base models
- common: Shared geolocation, coordinates, and address models
- graph: Knowledge graph and temporal models
- domain: Domain-specific models (attractions, holidays, projects, news, railway, hotel, orchestrators)
- ai: AI-related models (agent, graphrag)
"""

# Base models
from .base import (
    HealthResponse,
    ErrorResponse,
    ProvenanceMetadata,
    StatisticsResponse,
)

# Common models
from .common import (
    CoordinatesModel,
    MapLinksModel,
    AdministrativeAreasModel,
    AddressInfoModel,
    GeocodingMetadataModel,
    GeolocationModel,
    GooglePlaceDataModel,
    PaginatedResponse,
    QueryMetadata,
)

# Knowledge Graph models (from graph submodule)
from .graph.knowledge_graph import (
    QueryRequest,
    ReasonRequest,
    PredictRequest,
    ConstraintReasonRequest,
    WriteRequest,
    QueryResponse,
    ReasonResponse,
    PredictResponse,
    ConstraintReasonResponse,
    WriteResponse,
    ValidationResponse,
    ExportResponse,
    ExplainResponse,
)

# Attraction models (from domain submodule)
from .domain.attraction import (
    AttractionModel,
    CreateAttractionRequest,
    AttractionQueryRequest,
    AttractionResponse,
    CoordinatesModel,
    GeolocationModel,
    GooglePlaceDataModel,
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

# Hotel models (from domain submodule)
from .domain.hotel import (
    HotelType,
    HotelBase,
    HotelCreate,
    HotelSearchQuery,
    HotelRecommendationQuery,
    HotelStatistics,
)

# Orchestrator models (from domain submodule)
from .domain.orchestrator import (
    AccommodationSearchRequest,
    HotelItemResponse,
    OrchestratorSearchResponse,
)

from .domain.attraction_orchestrator import (
    AttractionSearchRequest,
    AttractionItem,
    AttractionSearchResponse,
)

from .domain.transport_orchestrator import (
    TransportSearchRequest,
    TransportOption,
    TransportSearchResponse,
)

# Agent models (from ai submodule)
from .ai.agent import (
    AgentSearchRequest,
    AgentPlanRequest,
)

# GraphRAG models (from ai submodule)
from .ai.graphrag import (
    IngestImmigrationDataRequest,
    IngestImmigrationDataResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    EnsureIndexResponse,
    GraphRAGStatistics,
    GraphNode,
    GraphRelationship,
    GraphExtraction,
    TravelWindow,
    VisaPolicyQueryRequest,
    EvidenceSource,
    RuleConditions,
    VisaRule,
    VisaPolicyResponse,
)

__all__ = [
    # Base
    "HealthResponse",
    "ErrorResponse",
    "ProvenanceMetadata",
    "StatisticsResponse",
    # Common
    "CoordinatesModel",
    "MapLinksModel",
    "AdministrativeAreasModel",
    "AddressInfoModel",
    "GeocodingMetadataModel",
    "GeolocationModel",
    "GooglePlaceDataModel",
    "PaginatedResponse",
    "QueryMetadata",
    "StatisticsResponse",
    # Knowledge Graph
    "QueryRequest",
    "ReasonRequest",
    "PredictRequest",
    "ConstraintReasonRequest",
    "WriteRequest",
    "QueryResponse",
    "ReasonResponse",
    "PredictResponse",
    "ConstraintReasonResponse",
    "WriteResponse",
    "ValidationResponse",
    "ExportResponse",
    "ExplainResponse",
    # Attractions
    "AttractionModel",
    "CreateAttractionRequest",
    "AttractionQueryRequest",
    "AttractionResponse",
    "CoordinatesModel",
    "GeolocationModel",
    "GooglePlaceDataModel",
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
    # Agent
    "AgentSearchRequest",
    "AgentPlanRequest",
    # GraphRAG
    "IngestImmigrationDataRequest",
    "IngestImmigrationDataResponse",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "EnsureIndexResponse",
    "GraphRAGStatistics",
    "GraphNode",
    "GraphRelationship",
    "GraphExtraction",
    # Visa Policy
    "TravelWindow",
    "VisaPolicyQueryRequest",
    "EvidenceSource",
    "RuleConditions",
    "VisaRule",
    "VisaPolicyResponse",
]
