"""GraphRAG API endpoints for entity extraction and RAG-based querying."""

import logging
import threading
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from database.manager import DatabaseManager
from services.graphrag import GraphRAGService
from core.config import settings
from models.ai.graphrag import (
    IngestImmigrationDataRequest,
    IngestImmigrationDataResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    EnsureIndexResponse,
    GraphRAGStatistics,
    VisaPolicyQueryRequest,
    VisaPolicyResponse,
    VisaRule,
    EvidenceSource,
    RuleConditions,
    TravelWindow
)
from api.dependencies import get_db_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graphrag", tags=["GraphRAG"])

# Global GraphRAG service instance with thread-safe initialization
_graphrag_service: Optional[GraphRAGService] = None
_service_lock = threading.Lock()


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


@router.post("/visa-policy", response_model=VisaPolicyResponse)
async def query_visa_policy(
    request: VisaPolicyQueryRequest,
    service: GraphRAGService = Depends(get_graphrag_service)
):
    """
    Query visa policy information without LLM generation.
    
    This endpoint retrieves relevant visa policy information using vector similarity search
    without invoking an LLM for answer generation. The response includes structured rules
    and evidence extracted from the knowledge graph.
    
    **Flow**:
    1. Builds semantic query from structured request
    2. Generates embedding for the query
    3. Retrieves top relevant chunks using vector similarity
    4. Extracts entities and rules from chunks
    5. Returns structured visa policy response
    
    **Status codes**:
    - `ok`: Successfully found relevant visa policy information
    - `needs_clarification`: Missing required information
    - `no_result`: No matching visa rules found
    - `error`: System error occurred
    """
    try:
        # Validate required fields for clarification
        if not request.nationality_country or not request.destination_country:
            return VisaPolicyResponse(
                status="needs_clarification",
                summary="Please specify both your nationality and destination country to determine visa eligibility.",
                rules=[],
                warnings=[]
            )
        
        if not request.purpose:
            return VisaPolicyResponse(
                status="needs_clarification",
                summary="Please specify your travel purpose (e.g., tourism, business) to determine visa eligibility.",
                rules=[],
                warnings=[]
            )
        
        # Build semantic query from structured input
        query_parts = [request.raw_text]
        
        # Add structured context for better semantic matching
        query_parts.append(f"Nationality: {request.nationality_country}")
        query_parts.append(f"Destination: {request.destination_country}")
        query_parts.append(f"Purpose: {request.purpose}")
        query_parts.append(f"Passport type: {request.passport_type}")
        query_parts.append(f"Stay duration: {request.intended_stay_days} days")
        
        if request.entry_type:
            query_parts.append(f"Entry type: {request.entry_type}")
        
        query_text = " | ".join(query_parts)
        
        logger.info(f"Querying visa policy for: {request.nationality_country} → {request.destination_country}")
        
        # Retrieve relevant chunks (top 10 with lower threshold for broader matching)
        chunks = service.retrieve_relevant_chunks(
            query_text=query_text,
            domain_name="Economic & Policy",
            top_k=10,
            min_score=0.4  # Lower threshold for better recall
        )
        
        # If no relevant chunks found
        if not chunks:
            return VisaPolicyResponse(
                status="no_result",
                destination_country=request.destination_country,
                nationality_country=request.nationality_country,
                purpose=request.purpose,
                passport_type=request.passport_type,
                travel_window=request.travel_window,
                intended_stay_days=request.intended_stay_days,
                summary=f"No visa policy information found for {request.nationality_country} nationals traveling to {request.destination_country} for {request.purpose}.",
                rules=[],
                warnings=["Please consult official immigration authorities for the most current visa requirements."]
            )
        
        # Extract rules and evidence from chunks
        rules = _extract_visa_rules_from_chunks(chunks, request)
        
        # Generate summary based on chunks
        summary = _generate_summary_from_chunks(chunks, request)
        
        # Generate warnings if applicable
        warnings = _generate_warnings(chunks, request)
        
        return VisaPolicyResponse(
            status="ok",
            destination_country=request.destination_country,
            nationality_country=request.nationality_country,
            purpose=request.purpose,
            passport_type=request.passport_type,
            travel_window=request.travel_window,
            intended_stay_days=request.intended_stay_days,
            summary=summary,
            rules=rules,
            warnings=warnings
        )
        
    except Exception as e:
        logger.error(f"Visa policy query failed: {e}", exc_info=True)
        return VisaPolicyResponse(
            status="error",
            summary=f"Unable to retrieve visa policy at this time: {str(e)}",
            rules=[],
            warnings=[]
        )


def _extract_visa_rules_from_chunks(
    chunks: list,
    request: VisaPolicyQueryRequest
) -> list[VisaRule]:
    """Extract structured visa rules from retrieved chunks."""
    rules = []
    
    # Process top chunks (prioritize by relevance score)
    for chunk in chunks[:5]:  # Use top 5 most relevant chunks
        text = chunk.get("text", "")
        source = chunk.get("source", "unknown")
        entities = chunk.get("entities", [])
        
        # Extract rule based on entities and text content
        rule = _create_rule_from_chunk(text, source, entities, request)
        if rule:
            rules.append(rule)
    
    # If no structured rules found, create a general rule from best chunk
    if not rules and chunks:
        best_chunk = chunks[0]
        rules.append(VisaRule(
            rule_type="general_information",
            title="Visa Information",
            details=best_chunk.get("text", "")[:500],  # Limit to 500 chars
            conditions=RuleConditions(
                nationality=request.nationality_country,
                purpose=request.purpose,
                passport_type=request.passport_type
            ),
            evidence=[EvidenceSource(
                source=best_chunk.get("source", "knowledge_base"),
                url="",
                quote=best_chunk.get("text", "")[:200]
            )]
        ))
    
    return rules


def _create_rule_from_chunk(
    text: str,
    source: str,
    entities: list,
    request: VisaPolicyQueryRequest
) -> VisaRule | None:
    """Create a visa rule from chunk text and entities."""
    text_lower = text.lower()
    
    # Detect rule type based on content
    rule_type = "general_information"
    title = "Visa Requirements"
    
    if any(term in text_lower for term in ["visa required", "eta required", "authorization required"]):
        rule_type = "eligibility"
        title = "Visa/ETA Requirement"
    elif any(term in text_lower for term in ["document", "passport", "photo", "application"]):
        rule_type = "requirements"
        title = "Required Documents"
    elif any(term in text_lower for term in ["fee", "cost", "payment", "usd", "rupees"]):
        rule_type = "fees"
        title = "Visa Fees"
    elif any(term in text_lower for term in ["process", "apply", "submit", "procedure"]):
        rule_type = "procedure"
        title = "Application Procedure"
    elif any(term in text_lower for term in ["duration", "stay", "days", "validity"]):
        rule_type = "duration"
        title = "Stay Duration"
    
    # Extract max stay days from entities or text
    max_stay_days = None
    for entity in entities:
        if entity.get("type") == "TimeFrame":
            props = entity.get("properties", {})
            if "duration_days" in props:
                max_stay_days = props["duration_days"]
    
    # Try to extract from text if not in entities
    if not max_stay_days:
        import re
        stay_pattern = r'(\d+)\s*days?'
        match = re.search(stay_pattern, text_lower)
        if match:
            max_stay_days = int(match.group(1))
    
    return VisaRule(
        rule_type=rule_type,
        title=title,
        details=text[:400],  # Limit details length
        conditions=RuleConditions(
            nationality=request.nationality_country,
            purpose=request.purpose,
            passport_type=request.passport_type,
            max_stay_days=max_stay_days
        ),
        evidence=[EvidenceSource(
            source=source,
            url="",
            quote=text[:200]
        )]
    )


def _generate_summary_from_chunks(
    chunks: list,
    request: VisaPolicyQueryRequest
) -> str:
    """Generate a summary from retrieved chunks."""
    if not chunks:
        return f"No visa information found for {request.nationality_country} nationals traveling to {request.destination_country}."
    
    # Use the best matching chunk for summary
    best_chunk = chunks[0]
    text = best_chunk.get("text", "")
    
    # Extract key sentence or create summary
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    if sentences:
        # Take first meaningful sentence
        summary = sentences[0] + "."
        if len(summary) > 200:
            summary = summary[:197] + "..."
        return summary
    
    return f"Visa information available for {request.nationality_country} nationals traveling to {request.destination_country} for {request.purpose}."


def _generate_warnings(
    chunks: list,
    request: VisaPolicyQueryRequest
) -> list[str]:
    """Generate warnings based on chunks and request."""
    warnings = []
    
    # Check if stay exceeds common limits
    if request.intended_stay_days > 90:
        warnings.append("Your intended stay exceeds 90 days. Extended stay visas may require additional documentation.")
    
    # Check for text mentioning restrictions or special conditions
    for chunk in chunks[:3]:
        text = chunk.get("text", "").lower()
        if any(term in text for term in ["restriction", "not eligible", "prohibited", "denied"]):
            warnings.append("Special restrictions may apply. Please verify eligibility with official sources.")
            break
    
    # Always add general warning
    warnings.append("This information is for reference only. Please verify with official immigration authorities before travel.")
    
    return warnings
