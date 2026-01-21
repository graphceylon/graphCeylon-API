"""Configuration management for the Knowledge Graph application."""

import os
from typing import Optional
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database connection settings."""
    
    neo4j_uri: str = "bolt://127.0.0.1:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    
    class Config:
        env_file = ".env"
        env_prefix = "KG_"
        extra = "ignore"  # Ignore extra fields from .env


class ApplicationSettings(BaseSettings):
    """FastAPI application settings."""
    
    app_title: str = "Sri Lanka Administrative Knowledge Graph"
    app_version: str = "0.1.0"
    app_description: str = "A semantic knowledge graph for Sri Lanka's administrative divisions"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_prefix = "KG_"
        extra = "ignore"  # Ignore extra fields from .env


class FilePathSettings(BaseSettings):
    """File path settings for data imports."""
    
    ontology_file: str = "neo4j/import/lk-tourism-ontology.ttl"
    shapes_file: str = "neo4j/import/lk-tourism-shapes.ttl"
    seed_file: str = "neo4j/import/scripts/seed_provinces_districts.cypher"
    
    class Config:
        env_file = ".env"
        env_prefix = "KG_"
        extra = "ignore"  # Ignore extra fields from .env


class AISettings(BaseSettings):
    """AI/ML configuration settings."""
    
    embedding_model_name: str = "all-MiniLM-L6-v2"
    vector_index_name: str = "attraction_embeddings"
    vector_dimensions: int = 384
    openai_api_key: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_prefix = "KG_"
        extra = "ignore"  # Ignore extra fields from .env


class GraphRAGSettings(BaseSettings):
    """GraphRAG-specific configuration."""
    
    chunk_size: int = 1000
    chunk_overlap: int = 100
    top_k: int = 5
    
    class Config:
        env_file = ".env"
        env_prefix = "KG_GRAPHRAG_"
        extra = "ignore"  # Ignore extra fields from .env


class Settings:
    """Unified settings container."""
    
    def __init__(self):
        self.database = DatabaseSettings()
        self.application = ApplicationSettings()
        self.file_paths = FilePathSettings()
        self.ai = AISettings()
        self.graphrag = GraphRAGSettings()
    
    # Backward compatibility properties
    @property
    def neo4j_uri(self) -> str:
        return self.database.neo4j_uri
    
    @property
    def neo4j_user(self) -> str:
        return self.database.neo4j_user
    
    @property
    def neo4j_password(self) -> str:
        return self.database.neo4j_password
    
    @property
    def app_title(self) -> str:
        return self.application.app_title
    
    @property
    def app_version(self) -> str:
        return self.application.app_version
    
    @property
    def app_description(self) -> str:
        return self.application.app_description
    
    @property
    def api_host(self) -> str:
        return self.application.api_host
    
    @property
    def api_port(self) -> int:
        return self.application.api_port
    
    @property
    def debug(self) -> bool:
        return self.application.debug
    
    @property
    def ontology_file(self) -> str:
        return self.file_paths.ontology_file
    
    @property
    def shapes_file(self) -> str:
        return self.file_paths.shapes_file
    
    @property
    def seed_file(self) -> str:
        return self.file_paths.seed_file
    
    @property
    def embedding_model_name(self) -> str:
        return self.ai.embedding_model_name
    
    @property
    def vector_index_name(self) -> str:
        return self.ai.vector_index_name
    
    @property
    def vector_dimensions(self) -> int:
        return self.ai.vector_dimensions
    
    @property
    def openai_api_key(self) -> Optional[str]:
        return self.ai.openai_api_key
    
    @property
    def graphrag_chunk_size(self) -> int:
        return self.graphrag.chunk_size
    
    @property
    def graphrag_chunk_overlap(self) -> int:
        return self.graphrag.chunk_overlap
    
    @property
    def graphrag_top_k(self) -> int:
        return self.graphrag.top_k


# Global settings instance
settings = Settings()
