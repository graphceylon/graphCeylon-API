"""Configuration management for the Knowledge Graph application."""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Neo4j Configuration
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    
    # FastAPI Configuration
    app_title: str = "Sri Lanka Administrative Knowledge Graph"
    app_version: str = "0.1.0"
    app_description: str = "A semantic knowledge graph for Sri Lanka's administrative divisions"
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    
    # File paths
    ontology_file: str = "neo4j/import/lk-tourism-ontology.ttl"
    shapes_file: str = "neo4j/import/lk-tourism-shapes.ttl"
    seed_file: str = "neo4j/import/scripts/seed_provinces_districts.cypher"

    # AI/ML Configuration
    embedding_model_name: str = "all-MiniLM-L6-v2"
    vector_index_name: str = "attraction_embeddings"
    vector_dimensions: int = 384
    openai_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    
    # GraphRAG Configuration
    graphrag_chunk_size: int = 1000
    graphrag_chunk_overlap: int = 100
    graphrag_top_k: int = 5
    
    # LLM Provider Configuration
    ingestion_llm_provider: str = "openai"  # Provider for data ingestion
    ingestion_llm_model: str = "gpt-4o-mini"  # Model for data ingestion
    query_llm_provider: str = "groq"  # Provider for querying
    query_llm_model: str = "llama-3.3-70b-versatile"  # Model for querying
    llm_temperature: float = 0
    
    class Config:
        # Use absolute path to find .env file in project root (parent of src)
        # src/core/config.py -> src/core -> src -> kg_service
        env_file = str(Path(__file__).resolve().parent.parent.parent / ".env")
        env_prefix = "KG_"
        extra = "ignore"  # Ignore extra fields from .env that aren't in the model

# Global settings instance
settings = Settings()
