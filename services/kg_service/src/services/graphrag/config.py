"""Configuration and constants for GraphRAG service."""

from typing import List


class GraphRAGConfig:
    """Configuration constants for GraphRAG operations."""
    
    # Schema definitions for Economic & Policy domain
    ALLOWED_NODES: List[str] = [
        "Policy", 
        "VisaType", 
        "Document", 
        "Requirement", 
        "Fee", 
        "Procedure", 
        "CitizenshipService", 
        "PassportService", 
        "ImmigrationService", 
        "Authority", 
        "Location", 
        "TimeFrame"
    ]
    
    ALLOWED_RELATIONSHIPS: List[str] = [
        "REQUIRES_DOCUMENT", 
        "HAS_FEE", 
        "HAS_REQUIREMENT", 
        "HAS_PROCEDURE",
        "APPLIES_TO", 
        "ISSUED_BY", 
        "PROCESSED_AT", 
        "TAKES_TIME",
        "PREREQUISITE_FOR", 
        "RELATED_TO", 
        "PART_OF", 
        "GOVERNED_BY"
    ]
    
    # Vector index configuration
    VECTOR_INDEX_NAME: str = "economic_policy_chunk_embeddings"
    
    # LLM configuration
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0
    
    # Text splitting configuration
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 100
    CHUNK_SEPARATORS: List[str] = ["\n\n", "\n", ". ", " ", ""]
    
    # Query configuration
    DEFAULT_TOP_K: int = 5
    DEFAULT_DOMAIN: str = "Economic & Policy"


# Global config instance
graphrag_config = GraphRAGConfig()
