"""Models package for the Knowledge Graph application."""

# Base models
from .base import (
    HealthResponse,
    ErrorResponse,
    ProvenanceMetadata,
    StatisticsResponse,
)

# Knowledge Graph models
from .knowledge_graph import (
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

# Attraction models
from .attractions import (
    AttractionModel,
    CreateAttractionRequest,
    AttractionQueryRequest,
    AttractionResponse,
    CoordinatesModel,
    GeolocationModel,
    GooglePlaceDataModel,
)

# Holiday models
from .holidays import (
    HolidayModel,
    CreateHolidayRequest,
    HolidayQueryRequest,
    HolidayResponse,
    TemporalStructureResponse,
)

# Project models
from .projects import (
    TourismProjectModel,
    CreateProjectRequest,
    ProjectQueryRequest,
    ProjectResponse,
)

# News models
from .news import (
    NewsArticleModel,
    CreateNewsRequest,
    NewsQueryRequest,
    NewsResponse,
)

# Agent models
from .agent import (
    AgentSearchRequest,
    AgentPlanRequest,
)

# GraphRAG models
from .graphrag import (
    IngestImmigrationDataRequest,
    IngestImmigrationDataResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    EnsureIndexResponse,
    GraphRAGStatistics,
    GraphNode,
    GraphRelationship,
    GraphExtraction,
)

__all__ = [
    # Base
    "HealthResponse",
    "ErrorResponse",
    "ProvenanceMetadata",
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
]
