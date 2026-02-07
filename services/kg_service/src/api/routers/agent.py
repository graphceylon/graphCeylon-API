"""Agent Interface Layer API endpoints."""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database.manager import DatabaseManager
from services.reasoning.symbolic import ReasoningOrchestrator
from api.dependencies import get_db_manager, get_reasoning_orchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agent Interface"])

# --- Request Models ---

class AgentSearchRequest(BaseModel):
    query: str
    limit: int = 5
    filters: Optional[Dict[str, Any]] = None

class AgentPlanRequest(BaseModel):
    intent: str
    waypoints: List[str]
    constraints: Optional[Dict[str, Any]] = None

# --- Endpoints ---

@router.post("/search")
async def agent_search(
    request: AgentSearchRequest,
    reasoning: ReasoningOrchestrator = Depends(get_reasoning_orchestrator)
):
    """
    Semantic search endpoint for agents.
    Returns ranked list of entities matching the natural language query.
    """
    logger.info(f"Agent search request: {request.query}")
    try:
        # Use the new vector reasoning capability
        response = reasoning.vector_reason_similar(request.query, top_k=request.limit)
        return response
    except Exception as e:
        logger.error(f"Agent search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/plan")
async def agent_plan(
    request: AgentPlanRequest,
    reasoning: ReasoningOrchestrator = Depends(get_reasoning_orchestrator)
):
    """
    Planning endpoint for agents.
    Validates paths and checks constraints between waypoints.
    """
    logger.info(f"Agent plan request: {request.intent} -> {request.waypoints}")
    try:
        if len(request.waypoints) < 2:
            raise HTTPException(status_code=400, detail="At least 2 waypoints required")
        
        start = request.waypoints[0]
        end = request.waypoints[1]
        
        # Use symbolic reasoning for path validation
        response = reasoning.symbolic_reason(start, end)
        
        # If constraints exist, apply them (simplified for MVP)
        if request.constraints:
            response["constraints_check"] = "Not implemented in MVP"
            
        return response
    except Exception as e:
        logger.error(f"Agent plan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/explain/{entity_id}")
async def agent_explain(
    entity_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Explainability endpoint.
    Returns provenance and context for a specific entity.
    """
    try:
        # Simple explanation: fetch node properties and immediate relationships
        cypher = """
        MATCH (n) WHERE id(n) = $id
        OPTIONAL MATCH (n)-[r]-(m)
        RETURN n, collect({rel: type(r), node: m.name, label: labels(m)[0]}) as context
        """
        # Note: entity_id comes as string, need to handle if it's an int ID or UUID
        # For this MVP we assume internal Neo4j ID for simplicity, but in prod use UUIDs
        try:
            nid = int(entity_id)
            result = db.execute_cypher(cypher, {"id": nid})
        except ValueError:
             # Try matching by name if not int
            cypher_name = """
            MATCH (n) WHERE n.name = $id OR n.title = $id
            OPTIONAL MATCH (n)-[r]-(m)
            RETURN n, collect({rel: type(r), node: m.name, label: labels(m)[0]}) as context
            """
            result = db.execute_cypher(cypher_name, {"id": entity_id})

        if not result:
            raise HTTPException(status_code=404, detail="Entity not found")
            
        return {
            "entity": result[0]["n"],
            "context": result[0]["context"],
            "provenance": "Sri Lanka Tourism Knowledge Graph v2.0"
        }
    except Exception as e:
        logger.error(f"Agent explain failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
