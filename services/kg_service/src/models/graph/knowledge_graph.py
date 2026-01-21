"""Knowledge Graph core models for provinces, districts, and reasoning."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# Request Models

class QueryRequest(BaseModel):
    """Request model for querying provinces or districts, or raw Cypher queries."""
    province: Optional[str] = Field(None, description="Name of the province to query")
    district: Optional[str] = Field(None, description="Name of the district to query")
    query: Optional[str] = Field(None, description="Raw Cypher query to execute")


class ReasonRequest(BaseModel):
    """Request model for reasoning between provinces and districts."""
    start_province: Optional[str] = Field(None, description="Starting province name")
    target_district: Optional[str] = Field(None, description="Target district name")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Optional constraints for enhanced reasoning")


class PredictRequest(BaseModel):
    """Request model for similarity predictions."""
    name: str = Field(..., description="Name to find similar entities for")
    label: str = Field("District", description="Node label to search within")
    top_k: int = Field(5, ge=1, le=20, description="Number of similar results to return")


class ConstraintReasonRequest(BaseModel):
    """Request model for constraint-based reasoning."""
    constraints: Dict[str, Any] = Field(..., description="Constraints for filtering (e.g., {'province': 'Western', 'min_districts': 3})")


class WriteRequest(BaseModel):
    """Request model for writing/updating nodes."""
    node_type: str = Field(..., description="Type of node (Province, District, etc.)")
    properties: Dict[str, Any] = Field(..., description="Node properties")
    source: str = Field(..., description="Data source for provenance")


# Response Models

class QueryResponse(BaseModel):
    """Response model for query operations."""
    result: Optional[Dict[str, Any]] = Field(None, description="Structured query result data")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="Raw Cypher query results")
    execution_time: float = Field(..., description="Query execution time in milliseconds")
    provenance: Optional[Dict[str, Any]] = Field(None, description="Provenance metadata")


class ReasonResponse(BaseModel):
    """Response model for reasoning operations."""
    feasible: bool = Field(..., description="Whether the reasoning found a valid path")
    explanations: List[Dict[str, Any]] = Field(..., description="Reasoning explanations")
    result: Optional[Dict[str, Any]] = Field(None, description="Reasoning result if feasible")
    predictive: Optional[Dict[str, Any]] = Field(None, description="Predictive results if not feasible")
    provenance: Optional[Dict[str, Any]] = Field(None, description="Provenance metadata")


class PredictResponse(BaseModel):
    """Response model for prediction operations."""
    result: List[Dict[str, Any]] = Field(..., description="Similar entities with scores")
    explanation: Dict[str, Any] = Field(..., description="Explanation of prediction method")


class ConstraintReasonResponse(BaseModel):
    """Response model for constraint-based reasoning."""
    result: List[Dict[str, Any]] = Field(..., description="Filtered results")
    explanation: Dict[str, Any] = Field(..., description="Explanation of constraints applied")


class WriteResponse(BaseModel):
    """Response model for write operations."""
    success: bool = Field(..., description="Whether the write operation succeeded")
    node_id: Optional[int] = Field(None, description="ID of the created/updated node")
    provenance: Dict[str, Any] = Field(..., description="Provenance metadata")


class ValidationResponse(BaseModel):
    """Response model for SHACL validation."""
    conforms: bool = Field(..., description="Whether data conforms to SHACL shapes")
    violations: List[Dict[str, Any]] = Field(..., description="List of validation violations")


class ExportResponse(BaseModel):
    """Response model for data export."""
    turtle_like: List[Dict[str, Any]] = Field(..., description="Exported data in turtle-like format")


class ExplainResponse(BaseModel):
    """Response model for evidence explanation."""
    evidence: Dict[str, Any] = Field(..., description="Evidence path data")
