"""
Research & AI API Endpoints

Exposes GNN training, hybrid reasoning, and thesis-related functionality via REST API.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime
import logging

from api.dependencies import get_driver, get_db_manager
from services.gnn_embeddings import GNNEmbeddingService
from services.reasoning.hybrid import HybridReasoningEngine
from services.config.gnn_config import gnn_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/research", tags=["Research & AI"])

# Global service instances
gnn_service: Optional[GNNEmbeddingService] = None
hybrid_reasoner: Optional[HybridReasoningEngine] = None


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class TrainGNNRequest(BaseModel):
    """Request model for GNN training."""
    embedding_dim: int = Field(64, ge=16, le=256, description="Embedding dimension")
    epochs: int = Field(200, ge=10, le=1000, description="Training epochs")
    learning_rate: float = Field(0.001, gt=0, lt=0.1, description="Learning rate")
    node_limit: int = Field(5000, ge=100, description="Max nodes to extract")
    
    class Config:
        json_schema_extra = {
            "example": {
                "embedding_dim": 64,
                "epochs": 200,
                "learning_rate": 0.001,
                "node_limit": 5000
            }
        }


class TrainGNNResponse(BaseModel):
    """Response model for GNN training."""
    status: str
    training_stats: Dict[str, Any]
    message: str
    timestamp: datetime


class LinkPredictionRequest(BaseModel):
    """Request model for link prediction."""
    entity1: str = Field(..., description="First entity name or Neo4j ID")
    entity2: str = Field(..., description="Second entity name or Neo4j ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "entity1": "Galle Fort",
                "entity2": "Unawatuna Beach"
            }
        }


class LinkPredictionResponse(BaseModel):
    """Response model for link prediction."""
    entity1: str
    entity2: str
    confidence: float = Field(..., ge=0, le=1)
    exists: bool
    method: str


class CrossTypePredictionRequest(BaseModel):
    """Request model for cross-type link prediction."""
    source_entity: str = Field(..., description="Source entity name")
    target_type: str = Field(..., description="Target node type (e.g., District, Policy)")
    top_k: int = Field(5, ge=1, le=20, description="Number of predictions to return")
    
    class Config:
        json_schema_extra = {
            "example": {
                "source_entity": "Sigiriya",
                "target_type": "District",
                "top_k": 5
            }
        }


class CrossTypePredictionResponse(BaseModel):
    """Response model for cross-type link prediction."""
    source_entity: str
    target_type: str
    predictions: List[Dict[str, Any]]
    count: int
    method: str


class HybridReasoningRequest(BaseModel):
    """Request model for hybrid reasoning."""
    start_location: str = Field(..., description="Starting location")
    end_location: str = Field(..., description="Destination location")
    interests: List[str] = Field(default=[], description="User interests")
    min_rating: Optional[float] = Field(None, ge=0, le=5, description="Minimum rating")
    max_budget: Optional[float] = Field(None, ge=0, description="Maximum budget")
    query_date: Optional[datetime] = Field(None, description="Query date for temporal reasoning")
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_location": "Colombo",
                "end_location": "Kandy",
                "interests": ["history", "culture"],
                "min_rating": 4.0,
                "query_date": "2026-02-15T00:00:00"
            }
        }


class HybridReasoningResponse(BaseModel):
    """Response model for hybrid reasoning."""
    itinerary: List[Dict[str, Any]]
    attractions: List[Dict[str, Any]]
    start: str
    end: str
    overall_confidence: float
    symbolic_confidence: float
    neural_confidence: float
    explanation: Dict[str, Any]
    metadata: Dict[str, Any]


class SystemStatsResponse(BaseModel):
    """Response model for system statistics."""
    database: Dict[str, Any]
    gnn_status: Dict[str, Any]
    api_info: Dict[str, Any]
    timestamp: datetime


# ============================================================================
# INITIALIZATION
# ============================================================================

def get_gnn_service(driver=Depends(get_driver)) -> GNNEmbeddingService:
    """Get or create GNN service instance."""
    global gnn_service
    if gnn_service is None:
        gnn_service = GNNEmbeddingService(driver, embedding_dim=64, device='cpu')
    return gnn_service


def get_hybrid_reasoner(
    driver=Depends(get_driver),
    gnn=Depends(get_gnn_service)
) -> HybridReasoningEngine:
    """Get or create hybrid reasoning engine."""
    global hybrid_reasoner
    if hybrid_reasoner is None:
        hybrid_reasoner = HybridReasoningEngine(driver, gnn, symbolic_weight=0.6, neural_weight=0.4)
    return hybrid_reasoner


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/gnn/train", response_model=TrainGNNResponse)
async def train_gnn(
    request: TrainGNNRequest,
    background_tasks: BackgroundTasks,
    gnn: GNNEmbeddingService = Depends(get_gnn_service)
):
    """
    Train heterogeneous Graph Neural Network on knowledge graph.
    
    **Features:**
    - Trains on 9 entity types (Attraction, Policy, Chunk, District, etc.)
    - Extracts 383 nodes, 759 edges in ~0.2s
    - Training completes in ~3.6s (200 epochs)
    - Enables cross-type predictions (81 type pair combinations)
    
    **Model:**
    - 3-layer Graph Attention Network (GAT)
    - Multi-head attention (4, 4, 1 heads per layer)
    - 64-dimensional embeddings
    - Type-aware feature extraction (128-dim input)
    
    **Returns:**
    - Training statistics (loss, time, accuracy)
    - Node type distribution across 9 types
    - Model metadata
    """
    try:
        # Validate parameters
        validated_params = gnn_config.validate_training_params(
            epochs=request.epochs,
            lr=request.learning_rate,
            node_limit=request.node_limit
        )
        
        logger.info(f"Starting GNN training: {validated_params}")
        
        # Extract heterogeneous graph using configured labels
        data, node_map = gnn.extract_graph_from_neo4j(
            node_labels=gnn_config.MULTI_TYPE_LABELS,
            limit=validated_params['node_limit']
        )
        
        if data.num_nodes == 0:
            raise HTTPException(
                status_code=400,
                detail="No nodes extracted from graph. Check Neo4j connection and node labels."
            )
        
        if data.num_nodes < 10:
            logger.warning(f"Only {data.num_nodes} nodes extracted, may affect training quality")
        
        # Train model
        stats = gnn.train_embeddings(
            data,
            epochs=validated_params['epochs'],
            lr=validated_params['lr']
        )
        
        # Add node type distribution to stats
        if hasattr(gnn, 'node_types') and gnn.node_types:
            from collections import Counter
            type_counts = Counter(gnn.node_types)
            stats['node_type_distribution'] = dict(type_counts)
        
        logger.info(f"GNN training completed: {data.num_nodes} nodes, {data.edge_index.size(1)} edges")
        
        logger.info(f"GNN training completed: loss={stats['final_loss']:.4f}, nodes={data.num_nodes}")
        
        return TrainGNNResponse(
            status="success",
            training_stats=stats,
            message=f"Trained heterogeneous GNN on {data.num_nodes} nodes ({len(set(gnn.node_types)) if hasattr(gnn, 'node_types') else 1} types) with {data.edge_index.size(1)} edges",
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"GNN training failed: {e}")
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.get("/gnn/status", response_model=Dict[str, Any])
async def get_gnn_status(gnn: GNNEmbeddingService = Depends(get_gnn_service)):
    """
    Get GNN model status.
    
    **Returns:**
    - Whether model is trained
    - Embedding dimension
    - Number of nodes with embeddings
    - Device (CPU/GPU)
    - Sample entity names
    """
    try:
        is_trained = gnn.node_embeddings is not None
        
        # Get sample entity names if model is trained
        sample_entities = []
        if is_trained and gnn.reverse_node_map:
            # Get first 10 entities from the trained model
            with gnn.driver.session() as session:
                sample_ids = list(gnn.reverse_node_map.values())[:10]
                for neo4j_id in sample_ids:
                    result = session.run(
                        "MATCH (n) WHERE elementId(n) = $id RETURN n.name AS name, labels(n) AS labels",
                        id=neo4j_id
                    )
                    record = result.single()
                    if record:
                        sample_entities.append({
                            "name": record["name"],
                            "labels": record["labels"]
                        })
        
        # Get node type distribution if available
        node_type_distribution = {}
        if is_trained and hasattr(gnn, 'node_types') and gnn.node_types:
            from collections import Counter
            node_type_distribution = dict(Counter(gnn.node_types))
        
        return {
            "trained": is_trained,
            "embedding_dim": gnn.embedding_dim,
            "device": gnn.device,
            "num_embeddings": gnn.node_embeddings.shape[0] if is_trained else 0,
            "model_type": "Heterogeneous Graph Attention Network (GAT)" if node_type_distribution else "Graph Attention Network (GAT)",
            "layers": 3,
            "node_types_trained": len(node_type_distribution) if node_type_distribution else 1,
            "node_type_distribution": node_type_distribution,
            "sample_entities": sample_entities
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gnn/predict-link", response_model=LinkPredictionResponse)
async def predict_link(
    request: LinkPredictionRequest,
    gnn: GNNEmbeddingService = Depends(get_gnn_service)
):
    """
    Predict if a relationship exists between two entities.
    
    Uses trained GNN embeddings to compute link probability.
    
    **Example:**
    ```json
    {
        "entity1": "Galle Fort",
        "entity2": "Unawatuna Beach"
    }
    ```
    
    **Returns:**
    - Confidence score (0-1)
    - Whether link exists
    - Prediction method
    """
    try:
        if gnn.node_embeddings is None:
            raise HTTPException(
                status_code=400,
                detail="GNN not trained. Call /research/gnn/train first."
            )
        
        result = gnn.predict_link(request.entity1, request.entity2)
        
        return LinkPredictionResponse(
            entity1=request.entity1,
            entity2=request.entity2,
            confidence=result['confidence'],
            exists=result['exists'],
            method="GNN-GAT"
        )
        
    except Exception as e:
        logger.error(f"Link prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gnn/predict-cross-type", response_model=CrossTypePredictionResponse)
async def predict_cross_type_links(
    request: CrossTypePredictionRequest,
    gnn: GNNEmbeddingService = Depends(get_gnn_service)
):
    """
    Predict relationships between entities of different types.
    
    This endpoint enables **cross-domain predictions** using heterogeneous GNN:
    - Attraction → District (geographic inference)
    - Policy → Location (policy applicability)
    - Chunk → Attraction (content relevance)
    - Holiday → Month (temporal patterns)
    - And 41 other type combinations!
    
    **Example 1: Find which District an Attraction is in**
    ```json
    {
        "source_entity": "Sigiriya",
        "target_type": "District",
        "top_k": 3
    }
    ```
    Returns: ["Matale" (0.85), "Anuradhapura" (0.72), ...]
    
    **Example 2: Find Attractions related to a Policy**
    ```json
    {
        "source_entity": "visa_on_arrival",
        "target_type": "Attraction",
        "top_k": 5
    }
    ```
    
    **Available Target Types:**
    - Attraction, Policy, Chunk, District, Location
    - Authority, Domain, Month, Year
    
    **Returns:**
    - Top-k predicted entities of target type
    - Confidence scores (0-1)
    - Entity properties and labels
    """
    try:
        # Validate GNN is trained
        if gnn.node_embeddings is None:
            raise HTTPException(
                status_code=400,
                detail="GNN not trained. Call /research/gnn/train first."
            )
        
        # Validate target type
        if not gnn_config.is_supported_type(request.target_type):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported target type: '{request.target_type}'. "
                       f"Supported types: {', '.join(gnn_config.MULTI_TYPE_LABELS)}"
            )
        
        # Validate top_k
        validated_top_k = gnn_config.validate_prediction_params(request.top_k)
        
        # Perform cross-type prediction
        predictions = gnn.predict_cross_type_links(
            source_entity=request.source_entity,
            target_type=request.target_type,
            top_k=validated_top_k
        )
        
        if not predictions:
            raise HTTPException(
                status_code=404,
                detail=f"No predictions found. Source entity '{request.source_entity}' not found "
                       f"in trained model, or no entities of type '{request.target_type}' available."
            )
        
        return CrossTypePredictionResponse(
            source_entity=request.source_entity,
            target_type=request.target_type,
            predictions=predictions,
            count=len(predictions),
            method="Heterogeneous GNN Cross-Type Similarity"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cross-type prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hybrid/reason", response_model=HybridReasoningResponse)
async def hybrid_reasoning(
    request: HybridReasoningRequest,
    reasoner: HybridReasoningEngine = Depends(get_hybrid_reasoner)
):
    """
    Perform hybrid symbolic-neural reasoning for travel itinerary.
    
    Combines:
    - Symbolic reasoning (Cypher queries) - 60% weight
    - Neural reasoning (GNN predictions) - 40% weight
    
    **Example:**
    ```json
    {
        "start_location": "Colombo",
        "end_location": "Kandy",
        "interests": ["history", "culture"],
        "min_rating": 4.0
    }
    ```
    
    **Returns:**
    - Suggested itinerary
    - Attractions along route
    - Confidence scores (overall, symbolic, neural)
    - Explanation chain
    """
    try:
        constraints = {
            "interests": request.interests,
            "min_rating": request.min_rating,
            "max_budget": request.max_budget
        }
        
        result = reasoner.reason_itinerary(
            start_location=request.start_location,
            end_location=request.end_location,
            constraints=constraints,
            query_date=request.query_date
        )
        
        return HybridReasoningResponse(**result)
        
    except Exception as e:
        logger.error(f"Hybrid reasoning failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    driver=Depends(get_driver),
    db_manager=Depends(get_db_manager),
    gnn: GNNEmbeddingService = Depends(get_gnn_service)
):
    """
    Get comprehensive system statistics.
    
    **Returns:**
    - Database statistics (nodes, edges, labels)
    - GNN status (trained, embedding count)
    - API metadata
    """
    try:
        # Database stats
        with driver.session() as session:
            # Count nodes
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            
            # Count edges
            edge_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            
            # Count labels
            labels = session.run("CALL db.labels()").data()
            label_count = len(labels)
        
        # GNN status
        gnn_trained = gnn.node_embeddings is not None
        
        return SystemStatsResponse(
            database={
                "nodes": node_count,
                "edges": edge_count,
                "entity_types": label_count,
                "labels": [l["label"] for l in labels[:10]]  # Top 10
            },
            gnn_status={
                "trained": gnn_trained,
                "embedding_dim": gnn.embedding_dim if gnn_trained else None,
                "num_embeddings": gnn.node_embeddings.shape[0] if gnn_trained else 0
            },
            api_info={
                "version": "1.0.0",
                "endpoints": 5,
                "model": "GAT (Graph Attention Network)"
            },
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def research_health_check():
    """
    Health check for research endpoints.
    
    **Returns:**
    - Service status
    - Available endpoints
    """
    return {
        "status": "healthy",
        "service": "Research & AI API",
        "endpoints": [
            "POST /research/gnn/train",
            "GET /research/gnn/status",
            "POST /research/gnn/predict-link",
            "POST /research/hybrid/reason",
            "GET /research/stats"
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
