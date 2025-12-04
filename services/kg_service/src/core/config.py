"""Configuration management for the Knowledge Graph application."""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Neo4j Configuration
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # FastAPI Configuration
    app_title: str = "GraphCeylon Knowledge Graph Service"
    app_version: str = "0.1.0"
    app_description: str = (
        "Knowledge graph service for Sri Lankan tourism data"
    )

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # AI/ML Configuration
    embedding_model_name: str = "all-MiniLM-L6-v2"
    vector_index_name: str = "attraction_embeddings"
    vector_dimensions: int = 384
    openai_api_key: Optional[str] = None

    # GraphRAG Configuration
    graphrag_chunk_size: int = 1000
    graphrag_chunk_overlap: int = 100
    graphrag_top_k: int = 5

    class Config:
        env_file = ".env"
        env_prefix = "KG_"


# Global settings instance
settings = Settings()
