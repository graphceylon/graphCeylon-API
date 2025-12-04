"""Pydantic models for GraphRAG API requests and responses."""

from typing import List, Dict, Any
from pydantic import BaseModel, Field


class IngestImmigrationDataRequest(BaseModel):
    """Request model for ingesting immigration data."""
    data_dir: str = Field(
        default="data/immigration",
        description="Directory containing immigration JSON files"
    )
    domain_name: str = Field(
        default="Economic & Policy",
        description="Domain to link the data to"
    )


class IngestImmigrationDataResponse(BaseModel):
    """Response model for immigration data ingestion."""
    success: bool = Field(..., description="Whether ingestion succeeded")
    statistics: dict = Field(..., description="Ingestion statistics")
    message: str = Field(..., description="Status message")


class RAGQueryRequest(BaseModel):
    """Request model for RAG-based querying."""
    question: str = Field(..., description="Question to ask the knowledge graph")
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of similar chunks to retrieve"
    )
    domain_name: str = Field(
        default="Economic & Policy",
        description="Domain to search within"
    )


class RAGQueryResponse(BaseModel):
    """Response model for RAG queries."""
    answer: str = Field(..., description="Generated answer")
    context: list = Field(..., description="Retrieved context chunks")
    metadata: dict = Field(..., description="Query metadata")


class EnsureIndexResponse(BaseModel):
    """Response model for ensuring vector index."""
    success: bool = Field(..., description="Whether operation succeeded")
    message: str = Field(..., description="Status message")


class GraphRAGStatistics(BaseModel):
    """Response model for GraphRAG statistics."""
    domain: str = Field(..., description="Domain name")
    chunk_count: int = Field(..., description="Total number of chunks")
    entity_types: List[Dict[str, Any]] = Field(..., description="Entity types with counts")
    relationship_types: List[Dict[str, Any]] = Field(..., description="Relationship types with counts")
    sample_chunks: List[Dict[str, Any]] = Field(default_factory=list, description="Sample chunks")


class GraphNode(BaseModel):
    """Represents a node in the knowledge graph."""
    id: str = Field(description="Unique identifier for the node")
    type: str = Field(description="Type of the node (Policy, Requirement, Document, VisaType, etc.)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Node properties")


class GraphRelationship(BaseModel):
    """Represents a relationship in the knowledge graph."""
    source_id: str = Field(description="ID of the source node")
    target_id: str = Field(description="ID of the target node")
    type: str = Field(description="Type of relationship")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Relationship properties")


class GraphExtraction(BaseModel):
    """Container for extracted graph elements."""
    nodes: List[GraphNode] = Field(
        default_factory=list,
        description="List of nodes extracted from the text"
    )
    relationships: List[GraphRelationship] = Field(
        default_factory=list,
        description="List of relationships between nodes"
    )
