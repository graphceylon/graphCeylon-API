from __future__ import annotations

from typing import Optional, Literal, Dict, Any
from pydantic import Field

from .base import BaseSchema


EvidenceMethod = Literal[
    "kg_query",
    "dataset_lookup",
    "api_call",
    "scrape",
    "model_inference",
    "manual_curation",
]


class Evidence(BaseSchema):
    source: str = Field(..., description="Name of source (e.g., 'Sri Lanka Immigration Dept', 'GTFS', 'TourismKG')")
    method: EvidenceMethod = Field(..., description="How this evidence was obtained")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score for this fact")

    # Optional traceability
    url: Optional[str] = Field(default=None, description="Source URL if applicable")
    document_id: Optional[str] = Field(default=None, description="Document identifier (PDF id, dataset id, etc.)")
    excerpt: Optional[str] = Field(default=None, description="Short supporting snippet (keep it short)")
    retrieved_at: Optional[str] = Field(default=None, description="ISO timestamp string, if you want")

    # Extra metadata: query, parameters, etc.
    meta: Dict[str, Any] = Field(default_factory=dict)
