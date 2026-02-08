"""Temporal and provenance models for knowledge graph entities."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TemporalMetadata(BaseModel):
    """Temporal metadata for entities with time-based validity."""
    
    valid_from: Optional[datetime] = Field(
        None, 
        description="Start of validity period (inclusive)"
    )
    valid_to: Optional[datetime] = Field(
        None, 
        description="End of validity period (exclusive, None means still valid)"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of last update"
    )
    created_at: Optional[datetime] = Field(
        None,
        description="Entity creation timestamp"
    )
    seasonal_availability: Optional[List[str]] = Field(
        None,
        description="Seasonal patterns: e.g., ['Nov-Mar', 'Apr-May-closed']"
    )
    closure_dates: Optional[List[str]] = Field(
        None,
        description="Specific closure dates in ISO format"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "valid_from": "2024-01-01T00:00:00Z",
                "valid_to": None,
                "last_updated": "2025-12-30T10:00:00Z",
                "seasonal_availability": ["Nov-Mar", "closed-during-Esala"],
                "closure_dates": ["2026-01-15", "2026-02-20"]
            }
        }


class ProvenanceMetadata(BaseModel):
    """Comprehensive provenance tracking for data lineage and trust."""
    
    source: str = Field(
        ..., 
        description="Primary data source identifier"
    )
    source_url: Optional[str] = Field(
        None,
        description="URL or reference to original data"
    )
    source_type: Optional[str] = Field(
        "manual",
        description="Type: api, scraper, manual, user_input, inference"
    )
    confidence: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 to 1.0)"
    )
    ingested_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when data was ingested"
    )
    verified: bool = Field(
        False,
        description="Whether data has been manually verified"
    )
    verified_by: Optional[str] = Field(
        None,
        description="User or system that verified the data"
    )
    verified_at: Optional[datetime] = Field(
        None,
        description="Verification timestamp"
    )
    license: Optional[str] = Field(
        None,
        description="Data license (CC-BY-SA, proprietary, etc.)"
    )
    extraction_method: Optional[str] = Field(
        None,
        description="Method used for extraction (NER, API, manual, etc.)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional custom metadata"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "source": "SLTDA Official Database",
                "source_url": "https://sltda.gov.lk/attractions/sigiriya",
                "source_type": "api",
                "confidence": 0.95,
                "ingested_at": "2025-12-30T10:00:00Z",
                "verified": True,
                "verified_by": "curator_001",
                "license": "CC-BY-SA-4.0",
                "extraction_method": "structured_api"
            }
        }


class TemporalProvenance(BaseModel):
    """Combined temporal and provenance metadata."""
    
    temporal: TemporalMetadata = Field(
        default_factory=TemporalMetadata,
        description="Temporal validity metadata"
    )
    provenance: ProvenanceMetadata = Field(
        ...,
        description="Data provenance and lineage"
    )
