"""Models package for the Knowledge Graph application.

Submodules:
    base    - Core API response models (HealthResponse, ErrorResponse, StatisticsResponse)
    common  - Shared geographic models (CoordinatesModel, GeolocationModel, etc.)
    graph   - Knowledge graph request/response models and temporal/provenance models
    domain  - Domain entities: attraction, holiday, hotel, news, project, railway
    ai      - GraphRAG and visa policy models

Import directly from submodules for clarity:
    from models.base import HealthResponse
    from models.domain.hotel import HotelCreate, AccommodationSearchRequest
    from models.graph.knowledge_graph import QueryRequest
    from models.ai.graphrag import RAGQueryRequest
"""
