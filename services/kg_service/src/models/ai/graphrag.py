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


# Visa Policy Query Models

class TravelWindow(BaseModel):
    """Travel window with start and end dates."""
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")


class VisaPolicyQueryRequest(BaseModel):
    """Request model for visa policy query without LLM."""
    intent: str = Field("info_visa_policy", description="Intent type (e.g., 'info_visa_policy')")
    user_id: str | None = Field(None, description="User identifier")
    session_id: str | None = Field(None, description="Session identifier")
    raw_text: str = Field(..., description="User's raw question text")
    nationality_country: str = Field(..., description="Nationality/passport country")
    destination_country: str = Field(..., description="Destination country")
    intended_stay_days: int | None = Field(None, description="Intended stay duration in days")
    travel_window: TravelWindow | None = Field(None, description="Travel date range")
    purpose: str = Field(..., description="Purpose of travel (tourism, business, etc.)")
    passport_type: str | None = Field(None, description="Type of passport (ordinary, diplomatic, etc.)")
    entry_type: str | None = Field(None, description="Entry type (single, multiple, etc.)")
    prior_visa_or_eta: str | None = Field(None, description="Prior visa or ETA status")
    ask_type: str | None = Field(None, description="Type of query (eligibility, requirements, etc.)")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Extra metadata")


class EvidenceSource(BaseModel):
    """Evidence source for a visa rule."""
    source: str = Field(..., description="Source name")
    url: str = Field(default="", description="Source URL")
    quote: str = Field(..., description="Relevant quote from source")


class RuleConditions(BaseModel):
    """Conditions for a visa rule."""
    nationality: str | None = Field(None, description="Applicable nationality")
    purpose: str | None = Field(None, description="Applicable purpose")
    passport_type: str | None = Field(None, description="Applicable passport type")
    max_stay_days: int | None = Field(None, description="Maximum stay days")


class VisaRule(BaseModel):
    """Visa rule with details and conditions."""
    rule_type: str = Field(..., description="Type of rule (eligibility, requirement, fee, etc.)")
    title: str = Field(..., description="Rule title")
    details: str = Field(..., description="Detailed description")
    conditions: RuleConditions = Field(default_factory=RuleConditions, description="Rule conditions")
    evidence: List[EvidenceSource] = Field(default_factory=list, description="Supporting evidence")


class VisaPolicyResponse(BaseModel):
    """Response model for visa policy query."""
    status: str = Field(..., description="Response status (ok, needs_clarification, no_result, error)")
    destination_country: str | None = Field(None, description="Destination country")
    nationality_country: str | None = Field(None, description="Nationality country")
    purpose: str | None = Field(None, description="Purpose of travel")
    passport_type: str | None = Field(None, description="Passport type")
    travel_window: TravelWindow | None = Field(None, description="Travel date range")
    intended_stay_days: int | None = Field(None, description="Intended stay days")
    summary: str = Field(..., description="Summary message")
    rules: List[VisaRule] = Field(default_factory=list, description="Applicable visa rules")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
