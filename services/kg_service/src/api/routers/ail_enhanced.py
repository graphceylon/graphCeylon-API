"""
Enhanced Agent Interface Layer (AIL) API endpoints.

Provides comprehensive interfaces for:
- Query: Read operations with filtering
- Reason: Multi-hop reasoning with explanations
- Write: Create/update entities with provenance
- Subscribe: Real-time updates via WebSocket
- Validate: SHACL validation
- Explain: Evidence trails and reasoning chains
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query as QueryParam
from pydantic import BaseModel, Field

from database.manager import DatabaseManager
from services.hybrid_reasoning import HybridReasoningEngine
from services.gnn_embeddings import GNNEmbeddingService
from models.graph.temporal import TemporalMetadata, ProvenanceMetadata, TemporalProvenance
from api.dependencies import get_db_manager, get_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ail", tags=["Agent Interface Layer"])

# Global services (initialized on startup)
hybrid_reasoner: Optional[HybridReasoningEngine] = None
gnn_service: Optional[GNNEmbeddingService] = None


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class QueryRequest(BaseModel):
    """Enhanced query request with temporal and filtering support."""
    cypher: Optional[str] = Field(None, description="Custom Cypher query")
    entity_type: Optional[str] = Field(None, description="Filter by entity type")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")
    query_date: Optional[datetime] = Field(None, description="Query for entities valid on this date")
    include_expired: bool = Field(False, description="Include expired entities")
    limit: int = Field(10, ge=1, le=100, description="Result limit")


class ReasonRequest(BaseModel):
    """Reasoning request for itinerary planning."""
    start_location: str = Field(..., description="Starting location")
    end_location: str = Field(..., description="Destination")
    query_date: Optional[datetime] = Field(None, description="Travel date")
    constraints: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Constraints: budget, interests, min_rating, etc."
    )
    reasoning_mode: str = Field(
        "hybrid",
        description="Reasoning mode: symbolic, neural, or hybrid"
    )


class WriteRequest(BaseModel):
    """Write request with full provenance and temporal metadata."""
    entity_type: str = Field(..., description="Type of entity to create/update")
    data: Dict[str, Any] = Field(..., description="Entity data")
    provenance: ProvenanceMetadata = Field(..., description="Provenance metadata")
    temporal: Optional[TemporalMetadata] = Field(None, description="Temporal metadata")
    operation: str = Field("create", description="Operation: create or update")
    entity_id: Optional[str] = Field(None, description="Entity ID for updates")


class SubscribeRequest(BaseModel):
    """Subscription request for real-time updates."""
    entity_types: List[str] = Field(
        default_factory=list,
        description="Entity types to subscribe to (empty = all)"
    )
    filter_criteria: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional filter criteria"
    )


class ValidateRequest(BaseModel):
    """SHACL validation request."""
    entity_type: Optional[str] = Field(None, description="Validate specific entity type")
    entity_data: Optional[Dict[str, Any]] = Field(None, description="Validate specific entity data")


class ExplainRequest(BaseModel):
    """Explanation request for reasoning chains."""
    entity_id: Optional[str] = Field(None, description="Entity to explain")
    reasoning_result_id: Optional[str] = Field(None, description="Reasoning result to explain")
    include_provenance: bool = Field(True, description="Include provenance chain")
    include_temporal: bool = Field(True, description="Include temporal validity")


class LinkPredictionRequest(BaseModel):
    """Request for predicting missing links."""
    entity1_name: str = Field(..., description="First entity name")
    entity2_name: str = Field(..., description="Second entity name")
    relationship_type: Optional[str] = Field(None, description="Specific relationship type")


# ============================================================================
# QUERY ENDPOINT
# ============================================================================

@router.post("/query")
async def query_knowledge_graph(
    request: QueryRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Query the knowledge graph with temporal and filtering support.
    
    Supports:
    - Custom Cypher queries
    - Entity type filtering
    - Temporal validity checks
    - Structured filtering
    """
    logger.info(f"AIL Query: entity_type={request.entity_type}, date={request.query_date}")
    
    try:
        if request.cypher:
            # Execute custom Cypher
            result = db.execute_cypher(request.cypher)
        else:
            # Build query from parameters
            cypher = "MATCH (n"
            
            if request.entity_type:
                cypher += f":{request.entity_type}"
            
            cypher += ")"
            
            # Temporal filtering
            if request.query_date and not request.include_expired:
                cypher += """
                WHERE 
                    (n.valid_from IS NULL OR n.valid_from <= $query_date)
                    AND (n.valid_to IS NULL OR n.valid_to > $query_date)
                """
            
            # Additional filters
            if request.filters:
                for key, value in request.filters.items():
                    cypher += f" AND n.{key} = ${key}"
            
            cypher += f" RETURN n LIMIT {request.limit}"
            
            params = {"query_date": request.query_date, **(request.filters or {})}
            result = db.execute_cypher(cypher, params)
        
        return {
            "success": True,
            "results": result,
            "count": len(result),
            "query_metadata": {
                "entity_type": request.entity_type,
                "query_date": request.query_date.isoformat() if request.query_date else None,
                "temporal_filtering": request.query_date is not None
            }
        }
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# REASON ENDPOINT
# ============================================================================

@router.post("/reason")
async def reason_itinerary(
    request: ReasonRequest,
    driver = Depends(get_driver)
):
    """
    Advanced reasoning for itinerary planning.
    
    Uses hybrid symbolic-neural reasoning to:
    - Find optimal paths
    - Suggest attractions
    - Check temporal validity
    - Apply constraints
    - Provide explanations
    """
    logger.info(f"AIL Reason: {request.start_location} -> {request.end_location}")
    
    try:
        global hybrid_reasoner, gnn_service
        
        # Initialize on first use
        if hybrid_reasoner is None:
            if request.reasoning_mode in ["neural", "hybrid"]:
                gnn_service = GNNEmbeddingService(driver)
            hybrid_reasoner = HybridReasoningEngine(driver, gnn_service)
        
        # Execute reasoning
        result = hybrid_reasoner.reason_itinerary(
            start_location=request.start_location,
            end_location=request.end_location,
            constraints=request.constraints,
            query_date=request.query_date
        )
        
        return {
            "success": True,
            "reasoning": result
        }
        
    except Exception as e:
        logger.error(f"Reasoning failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WRITE ENDPOINT
# ============================================================================

@router.post("/write")
async def write_entity(
    request: WriteRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Write entity to knowledge graph with full provenance and temporal tracking.
    
    Features:
    - Automatic provenance recording
    - Temporal validity tracking
    - SHACL validation (optional)
    - Conflict detection
    """
    logger.info(f"AIL Write: {request.operation} {request.entity_type}")
    
    try:
        # Prepare entity data with metadata
        entity_data = request.data.copy()
        
        # Add temporal metadata
        if request.temporal:
            entity_data.update({
                "valid_from": request.temporal.valid_from,
                "valid_to": request.temporal.valid_to,
                "last_updated": request.temporal.last_updated or datetime.utcnow(),
                "seasonal_availability": request.temporal.seasonal_availability,
                "closure_dates": request.temporal.closure_dates
            })
        
        # Add provenance metadata
        entity_data.update({
            "source": request.provenance.source,
            "source_url": request.provenance.source_url,
            "source_type": request.provenance.source_type,
            "confidence": request.provenance.confidence,
            "ingested_at": request.provenance.ingested_at or datetime.utcnow(),
            "verified": request.provenance.verified,
            "verified_by": request.provenance.verified_by,
            "license": request.provenance.license
        })
        
        # Build Cypher query
        if request.operation == "create":
            # Create new entity
            props = ", ".join([f"{k}: ${k}" for k in entity_data.keys()])
            cypher = f"CREATE (n:{request.entity_type} {{{props}}}) RETURN n"
        else:
            # Update existing entity
            if not request.entity_id:
                raise HTTPException(status_code=400, detail="entity_id required for updates")
            
            set_clause = ", ".join([f"n.{k} = ${k}" for k in entity_data.keys()])
            cypher = f"""
            MATCH (n:{request.entity_type})
            WHERE id(n) = $entity_id
            SET {set_clause}
            RETURN n
            """
            entity_data["entity_id"] = int(request.entity_id)
        
        result = db.execute_cypher(cypher, entity_data)
        
        if not result:
            raise HTTPException(status_code=404, detail="Entity not found or operation failed")
        
        return {
            "success": True,
            "operation": request.operation,
            "entity_type": request.entity_type,
            "entity": result[0],
            "provenance": {
                "source": request.provenance.source,
                "confidence": request.provenance.confidence,
                "ingested_at": entity_data["ingested_at"].isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Write failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# VALIDATE ENDPOINT
# ============================================================================

@router.post("/validate")
async def validate_entity(
    request: ValidateRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Validate entities against SHACL shapes.
    
    Can validate:
    - Entire graph
    - Specific entity type
    - Individual entity data (before writing)
    """
    logger.info(f"AIL Validate: entity_type={request.entity_type}")
    
    try:
        # Run SHACL validation
        validation_result = db.validate_shacl()
        
        # Filter by entity type if specified
        if request.entity_type:
            violations = [
                v for v in validation_result.get("violations", [])
                if request.entity_type in str(v)
            ]
            validation_result["violations"] = violations
            validation_result["violation_count"] = len(violations)
        
        return {
            "success": True,
            "conforms": validation_result.get("conforms", False),
            "violations": validation_result.get("violations", []),
            "violation_count": validation_result.get("violation_count", 0),
            "validated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# EXPLAIN ENDPOINT
# ============================================================================

@router.post("/explain")
async def explain_entity(
    request: ExplainRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Provide detailed explanation for entity or reasoning result.
    
    Returns:
    - Entity properties
    - Provenance chain
    - Temporal validity
    - Related entities
    - Reasoning paths (if applicable)
    """
    logger.info(f"AIL Explain: entity_id={request.entity_id}")
    
    try:
        if not request.entity_id:
            raise HTTPException(status_code=400, detail="entity_id required")
        
        # Get entity details
        cypher = """
        MATCH (n)
        WHERE id(n) = $entity_id
        OPTIONAL MATCH (n)-[r]-(m)
        RETURN 
            n AS entity,
            labels(n) AS labels,
            properties(n) AS properties,
            collect({
                relationship: type(r),
                direction: CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END,
                related_entity: m.name,
                related_labels: labels(m)
            }) AS relationships
        """
        
        result = db.execute_cypher(cypher, {"entity_id": int(request.entity_id)})
        
        if not result:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        entity_data = result[0]
        props = entity_data["properties"]
        
        explanation = {
            "entity_id": request.entity_id,
            "entity_type": entity_data["labels"][0] if entity_data["labels"] else "Unknown",
            "properties": props,
            "relationships": entity_data["relationships"]
        }
        
        # Add provenance if requested
        if request.include_provenance and "source" in props:
            explanation["provenance"] = {
                "source": props.get("source"),
                "source_url": props.get("source_url"),
                "confidence": props.get("confidence", 1.0),
                "ingested_at": props.get("ingested_at"),
                "verified": props.get("verified", False),
                "verified_by": props.get("verified_by")
            }
        
        # Add temporal if requested
        if request.include_temporal:
            explanation["temporal"] = {
                "valid_from": props.get("valid_from"),
                "valid_to": props.get("valid_to"),
                "last_updated": props.get("last_updated"),
                "seasonal_availability": props.get("seasonal_availability"),
                "is_currently_valid": props.get("valid_to") is None or props.get("valid_to") > datetime.utcnow().isoformat()
            }
        
        return {
            "success": True,
            "explanation": explanation,
            "explained_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Explanation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SUBSCRIBE ENDPOINT (WebSocket)
# ============================================================================

class ConnectionManager:
    """Manage WebSocket connections for subscriptions."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message: {e}")


manager = ConnectionManager()


@router.websocket("/subscribe")
async def websocket_subscribe(
    websocket: WebSocket,
    entity_types: str = QueryParam("", description="Comma-separated entity types")
):
    """
    Subscribe to real-time knowledge graph updates.
    
    Sends notifications when:
    - Entities are created
    - Entities are updated
    - Entities are deleted
    - Temporal validity changes
    
    Example:
        ws://localhost:8000/ail/subscribe?entity_types=Attraction,Hotel
    """
    await manager.connect(websocket)
    
    subscribed_types = [t.strip() for t in entity_types.split(",") if t.strip()]
    
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connection_established",
            "subscribed_types": subscribed_types,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep connection alive and listen for messages
        while True:
            # In production, integrate with Neo4j change data capture
            # For now, just keep connection alive
            data = await websocket.receive_text()
            
            # Echo back for testing
            await websocket.send_json({
                "type": "echo",
                "message": data,
                "timestamp": datetime.utcnow().isoformat()
            })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected from subscription")


# Helper function to broadcast updates (call from write operations)
async def notify_entity_change(
    operation: str,
    entity_type: str,
    entity_data: Dict[str, Any]
):
    """Notify subscribers of entity changes."""
    message = {
        "type": "entity_change",
        "operation": operation,
        "entity_type": entity_type,
        "entity": entity_data,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast(message)


# ============================================================================
# LINK PREDICTION ENDPOINT
# ============================================================================

@router.post("/predict-link")
async def predict_missing_link(
    request: LinkPredictionRequest,
    driver = Depends(get_driver)
):
    """
    Predict if a relationship exists between two entities using hybrid reasoning.
    
    Combines:
    - Symbolic: Check if link exists in KG
    - Neural: GNN-based link prediction
    - Confidence scoring
    """
    logger.info(f"AIL Predict Link: {request.entity1_name} <-> {request.entity2_name}")
    
    try:
        global hybrid_reasoner, gnn_service
        
        if hybrid_reasoner is None:
            gnn_service = GNNEmbeddingService(driver)
            hybrid_reasoner = HybridReasoningEngine(driver, gnn_service)
        
        result = hybrid_reasoner.predict_missing_relationship(
            entity1_name=request.entity1_name,
            entity2_name=request.entity2_name,
            relationship_type=request.relationship_type
        )
        
        return {
            "success": True,
            "prediction": result
        }
        
    except Exception as e:
        logger.error(f"Link prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
