"""
DEPRECATED: This file is maintained for backward compatibility only.
Please import from the organized model files instead:
- base_models.py
- attraction_models.py
- holiday_models.py
- project_models.py
- news_models.py
- reasoning_models.py
"""

# Re-export from organized modules for backward compatibility

# Base models
from .base import (
    HealthResponse,
    ErrorResponse,
    StatisticsResponse,
)

# Knowledge Graph models
from .knowledge_graph import (
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

# Attraction models
from .attractions import (
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
]
