"""GraphRAG API endpoints for entity extraction and RAG-based querying."""

import logging
import threading
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from database.manager import DatabaseManager
from services.graphrag import GraphRAGService
from core.config import settings
from models.graphrag import (
    IngestImmigrationDataRequest,
    IngestImmigrationDataResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    EnsureIndexResponse,
    GraphRAGStatistics
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graphrag", tags=["GraphRAG"])

# Global GraphRAG service instance with thread-safe initialization
_graphrag_service: Optional[GraphRAGService] = None
_service_lock = threading.Lock()


def get_db_manager() -> DatabaseManager:
    """Dependency to get database manager (will be overridden by main.py)."""
    raise HTTPException(status_code=503, detail="Database manager not initialized")


def get_graphrag_service(db: DatabaseManager = Depends(get_db_manager)) -> GraphRAGService:
    """Get or create GraphRAG service instance (thread-safe singleton)."""
    global _graphrag_service
    
    # Double-checked locking pattern for thread-safe singleton
    if _graphrag_service is None:
        with _service_lock:
            # Check again inside the lock
            if _graphrag_service is None:
                # Validate that required API keys are configured
                if settings.ingestion_llm_provider == "openai" and not settings.openai_api_key:
                    raise HTTPException(
                        status_code=503, 
                        detail="OpenAI API key not configured for ingestion. Set KG_OPENAI_API_KEY in .env file."
                    )
                
                if settings.ingestion_llm_provider == "groq" and not settings.groq_api_key:
                    raise HTTPException(
                        status_code=503, 
                        detail="Groq API key not configured for ingestion. Set KG_GROQ_API_KEY in .env file."
                    )
                
                if settings.query_llm_provider == "openai" and not settings.openai_api_key:
                    raise HTTPException(
                        status_code=503, 
                        detail="OpenAI API key not configured for queries. Set KG_OPENAI_API_KEY in .env file."
                    )
                
                if settings.query_llm_provider == "groq" and not settings.groq_api_key:
                    raise HTTPException(
                        status_code=503, 
                        detail="Groq API key not configured for queries. Set KG_GROQ_API_KEY in .env file."
                    )
                
                _graphrag_service = GraphRAGService(driver=db.driver)
                logger.info("GraphRAG service initialized")
    
    return _graphrag_service


# API Endpoints

@router.post("/ingest", response_model=IngestImmigrationDataResponse)
async def ingest_immigration_data(
    request: IngestImmigrationDataRequest,
    service: GraphRAGService = Depends(get_graphrag_service)
):
    """
    Ingest immigration data from JSON files into the knowledge graph.
    
    This endpoint:
    1. Reads JSON files from the specified directory
    2. Extracts text content and splits into chunks
    3. Uses LLM to extract entities and relationships
    4. Stores chunks with embeddings in Neo4j
    5. Links all data to the Economic & Policy domain
    
    **Note**: Requires OPENAI_API_KEY environment variable.
    """
    try:
        logger.info(f"Starting immigration data ingestion from: {request.data_dir}")
        
        stats = service.ingest_immigration_data(
            data_dir=request.data_dir,
            domain_name=request.domain_name
        )
        
        return IngestImmigrationDataResponse(
            success=True,
            statistics=stats,
            message=f"Successfully ingested {stats['files_processed']} files"
        )
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Immigration data ingestion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}"
        )


@router.post("/query", response_model=RAGQueryResponse)
async def query_with_rag(
    request: RAGQueryRequest,
    service: GraphRAGService = Depends(get_graphrag_service)
):
    """
    Query the knowledge graph using RAG (Retrieval-Augmented Generation).
    
    This endpoint:
    1. Generates an embedding for the question
    2. Performs vector similarity search to find relevant chunks
    3. Retrieves linked entities from the graph
    4. Uses LLM to generate a natural language answer
    
    All searches are scoped to the Economic & Policy domain.
    
    **Note**: Requires OPENAI_API_KEY environment variable.
    """
    try:
        logger.info(f"RAG query: {request.question}")
        
        result = service.query(
            question=request.question,
            top_k=request.top_k,
            domain_name=request.domain_name
        )
        
        return RAGQueryResponse(
            answer=result["answer"],
            context=result["context"],
            metadata=result["metadata"]
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {str(e)}"
        )


@router.post("/ensure-index", response_model=EnsureIndexResponse)
async def ensure_vector_index(
    service: GraphRAGService = Depends(get_graphrag_service)
):
    """
    Ensure that the vector index for chunk embeddings exists.
    
    This endpoint creates the vector index if it doesn't exist, or confirms
    it's already present. The index enables fast similarity search for RAG queries.
    """
    try:
        logger.info("Ensuring vector index exists")
        
        result = service.ensure_vector_index()
        
        return EnsureIndexResponse(
            success=result["success"],
            message=result["message"]
        )
        
    except Exception as e:
        logger.error(f"Failed to ensure vector index: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Index creation failed: {str(e)}"
        )


@router.get("/statistics", response_model=GraphRAGStatistics)
async def get_graphrag_statistics(
    service: GraphRAGService = Depends(get_graphrag_service)
):
    """
    Get statistics about the GraphRAG knowledge graph.
    
    Returns counts of:
    - Chunks in Economic & Policy domain
    - Entities by type
    - Relationships by type
    """
    try:
        stats = service.get_statistics()
        
        return GraphRAGStatistics(
            domain=stats["domain"],
            chunk_count=stats["chunk_count"],
            entity_types=stats["entity_types"],
            relationship_types=stats["relationship_types"],
            sample_chunks=stats.get("sample_chunks", [])
        )
        
    except Exception as e:
        logger.error(f"Failed to get GraphRAG statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Statistics query failed: {str(e)}"
        )
