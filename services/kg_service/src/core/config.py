"""Configuration management for the Knowledge Graph application.

Industry best practices:
- Single source of truth for all configuration
- Environment variable support with type validation
- Modular organization with logical grouping
- Clear documentation and sensible defaults
"""

import os

from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
]


def get_cors_origins() -> list[str]:
    """Return configured CORS origins with localhost defaults for dev."""
    configured = os.getenv("KG_CORS_ORIGIN") or os.getenv("CORS_ORIGIN")
    if not configured:
        return DEFAULT_CORS_ORIGINS.copy()

    origins = [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    if not origins:
        return DEFAULT_CORS_ORIGINS.copy()

    for default_origin in DEFAULT_CORS_ORIGINS:
        if default_origin not in origins:
            origins.append(default_origin)

    return origins


class DatabaseConfig(BaseSettings):
    """Neo4j database configuration."""
    
    neo4j_uri: str = Field(
        default="bolt://127.0.0.1:7687",
        description="Neo4j connection URI"
    )
    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j username"
    )
    neo4j_password: str = Field(
        default="password",
        description="Neo4j password"
    )
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_prefix="KG_",
        extra="ignore",
        case_sensitive=False,
    )
    
    @field_validator('neo4j_uri')
    @classmethod
    def validate_uri(cls, v: str) -> str:
        """Ensure URI starts with bolt:// or neo4j://."""
        if not (v.startswith('bolt://') or v.startswith('neo4j://')):
            raise ValueError('Neo4j URI must start with bolt:// or neo4j://')
        return v


class APIConfig(BaseSettings):
    """FastAPI application configuration."""
    
    app_title: str = Field(
        default="Sri Lanka Tourism Knowledge Graph",
        description="API title"
    )
    app_version: str = Field(
        default="0.1.0",
        description="API version"
    )
    app_description: str = Field(
        default="A semantic knowledge graph for Sri Lanka's tourism ecosystem",
        description="API description"
    )
    api_host: str = Field(
        default="0.0.0.0",
        description="API host address"
    )
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="API port number"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_prefix="KG_",
        extra="ignore",
        case_sensitive=False,
    )


class FilePaths(BaseSettings):
    """File paths for data imports and resources."""
    
    ontology_file: str = Field(
        default="neo4j/import/data/lk-admin.ttl",
        description="RDF/OWL ontology file path"
    )
    shapes_file: str = Field(
        default="neo4j/import/data/lk-shapes.ttl",
        description="SHACL shapes file path"
    )
    seed_file: str = Field(
        default="neo4j/import/scripts/seed_provinces_districts.cypher",
        description="Initial seed data Cypher script"
    )
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_prefix="KG_",
        extra="ignore",
        case_sensitive=False,
    )


class AIConfig(BaseSettings):
    """AI/ML and embedding configuration."""
    
    # Embedding Configuration
    embedding_model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence transformer model for embeddings"
    )
    vector_index_name: str = Field(
        default="attraction_embeddings",
        description="Neo4j vector index name"
    )
    vector_dimensions: int = Field(
        default=384,
        ge=1,
        description="Embedding vector dimensions"
    )
    
    # LLM API Keys
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key"
    )
    groq_api_key: Optional[str] = Field(
        default=None,
        description="Groq API key"
    )
    
    # LLM Provider Configuration
    ingestion_llm_provider: str = Field(
        default="openai",
        description="LLM provider for data ingestion (openai/groq)"
    )
    ingestion_llm_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model for data ingestion"
    )
    query_llm_provider: str = Field(
        default="groq",
        description="LLM provider for querying (openai/groq)"
    )
    query_llm_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="LLM model for querying"
    )
    llm_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="LLM temperature for generation"
    )
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_prefix="KG_",
        extra="ignore",
        case_sensitive=False,
    )
    
    @field_validator('ingestion_llm_provider', 'query_llm_provider')
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate LLM provider is supported."""
        allowed = ['openai', 'groq']
        if v.lower() not in allowed:
            raise ValueError(f'LLM provider must be one of {allowed}')
        return v.lower()


class GraphRAGConfig(BaseSettings):
    """GraphRAG-specific configuration."""
    
    chunk_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Text chunk size for document processing"
    )
    chunk_overlap: int = Field(
        default=100,
        ge=0,
        le=1000,
        description="Overlap between chunks"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of top results to retrieve"
    )
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_prefix="KG_",
        extra="ignore",
        case_sensitive=False,
    )
    
    @field_validator('chunk_overlap')
    @classmethod
    def validate_overlap(cls, v: int, info) -> int:
        """Ensure overlap is less than chunk size."""
        # Note: info.data may contain chunk_size if validated before overlap
        if 'chunk_size' in info.data and v >= info.data['chunk_size']:
            raise ValueError('chunk_overlap must be less than chunk_size')
        return v


class Settings(BaseSettings):
    """Main settings class aggregating all configuration sections.
    
    This class provides a centralized configuration management following
    the 12-factor app methodology with environment variable support.
    
    Environment variables should be prefixed with KG_ (e.g., KG_NEO4J_URI)
    """
    
    # Nested configuration groups
    database: DatabaseConfig = DatabaseConfig()
    api: APIConfig = APIConfig()
    file_paths: FilePaths = FilePaths()
    ai: AIConfig = AIConfig()
    graphrag: GraphRAGConfig = GraphRAGConfig()
    
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_prefix="KG_",
        env_nested_delimiter="__",  # Allows KG_DATABASE__NEO4J_URI
        extra="ignore",
        case_sensitive=False,
    )
    
    # Backward compatibility: Flat access to nested settings
    @property
    def neo4j_uri(self) -> str:
        """Neo4j connection URI (backward compatibility)."""
        return self.database.neo4j_uri
    
    @property
    def neo4j_user(self) -> str:
        """Neo4j username (backward compatibility)."""
        return self.database.neo4j_user
    
    @property
    def neo4j_password(self) -> str:
        """Neo4j password (backward compatibility)."""
        return self.database.neo4j_password
    
    @property
    def app_title(self) -> str:
        """API title (backward compatibility)."""
        return self.api.app_title
    
    @property
    def app_version(self) -> str:
        """API version (backward compatibility)."""
        return self.api.app_version
    
    @property
    def app_description(self) -> str:
        """API description (backward compatibility)."""
        return self.api.app_description
    
    @property
    def api_host(self) -> str:
        """API host (backward compatibility)."""
        return self.api.api_host
    
    @property
    def api_port(self) -> int:
        """API port (backward compatibility)."""
        return self.api.api_port
    
    @property
    def debug(self) -> bool:
        """Debug mode (backward compatibility)."""
        return self.api.debug

    @property
    def cors_origins(self) -> list[str]:
        """Allowed CORS origins for browser clients."""
        return get_cors_origins()
    
    @property
    def ontology_file(self) -> str:
        """Ontology file path (backward compatibility)."""
        return self.file_paths.ontology_file
    
    @property
    def shapes_file(self) -> str:
        """Shapes file path (backward compatibility)."""
        return self.file_paths.shapes_file
    
    @property
    def seed_file(self) -> str:
        """Seed file path (backward compatibility)."""
        return self.file_paths.seed_file
    
    @property
    def embedding_model_name(self) -> str:
        """Embedding model name (backward compatibility)."""
        return self.ai.embedding_model_name
    
    @property
    def vector_index_name(self) -> str:
        """Vector index name (backward compatibility)."""
        return self.ai.vector_index_name
    
    @property
    def vector_dimensions(self) -> int:
        """Vector dimensions (backward compatibility)."""
        return self.ai.vector_dimensions
    
    @property
    def openai_api_key(self) -> Optional[str]:
        """OpenAI API key (backward compatibility)."""
        return self.ai.openai_api_key
    
    @property
    def groq_api_key(self) -> Optional[str]:
        """Groq API key (backward compatibility)."""
        return self.ai.groq_api_key
    
    @property
    def ingestion_llm_provider(self) -> str:
        """Ingestion LLM provider (backward compatibility)."""
        return self.ai.ingestion_llm_provider
    
    @property
    def ingestion_llm_model(self) -> str:
        """Ingestion LLM model (backward compatibility)."""
        return self.ai.ingestion_llm_model
    
    @property
    def query_llm_provider(self) -> str:
        """Query LLM provider (backward compatibility)."""
        return self.ai.query_llm_provider
    
    @property
    def query_llm_model(self) -> str:
        """Query LLM model (backward compatibility)."""
        return self.ai.query_llm_model
    
    @property
    def llm_temperature(self) -> float:
        """LLM temperature (backward compatibility)."""
        return self.ai.llm_temperature
    
    @property
    def graphrag_chunk_size(self) -> int:
        """GraphRAG chunk size (backward compatibility)."""
        return self.graphrag.chunk_size
    
    @property
    def graphrag_chunk_overlap(self) -> int:
        """GraphRAG chunk overlap (backward compatibility)."""
        return self.graphrag.chunk_overlap
    
    @property
    def graphrag_top_k(self) -> int:
        """GraphRAG top K (backward compatibility)."""
        return self.graphrag.top_k


# Global settings instance
settings = Settings()
