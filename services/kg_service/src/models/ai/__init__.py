"""AI models submodule for agent and GraphRAG operations."""

from .agent import (
    AgentSearchRequest,
    AgentPlanRequest,
)

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
    TravelWindow,
    VisaPolicyQueryRequest,
    EvidenceSource,
    RuleConditions,
    VisaRule,
    VisaPolicyResponse,
)

__all__ = [
    # Agent models
    "AgentSearchRequest",
    "AgentPlanRequest",
    # GraphRAG models
    "IngestImmigrationDataRequest",
    "IngestImmigrationDataResponse",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "EnsureIndexResponse",
    "GraphRAGStatistics",
    "GraphNode",
    "GraphRelationship",
    "GraphExtraction",
    # Visa Policy models
    "TravelWindow",
    "VisaPolicyQueryRequest",
    "EvidenceSource",
    "RuleConditions",
    "VisaRule",
    "VisaPolicyResponse",
]
