"""API handlers for core knowledge graph operations."""

import logging
import time
import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from ...database.manager import DatabaseManager
from ...services.reasoning import ReasoningOrchestrator
from ...models.knowledge_graph import (
    QueryRequest,
    QueryResponse,
    ReasonRequest,
    ReasonResponse,
    PredictRequest,
    PredictResponse,
    ConstraintReasonRequest,
    ConstraintReasonResponse,
    WriteRequest,
    WriteResponse,
    ValidationResponse,
    ExportResponse,
    ExplainResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kg", tags=["Knowledge Graph"])


def get_db_manager() -> DatabaseManager:
    """Dependency to get database manager (will be overridden by main.py)."""
    raise HTTPException(status_code=503, detail="Database manager not initialized")


def get_reasoning_orchestrator() -> ReasoningOrchestrator:
    """Dependency to get reasoning orchestrator (will be overridden by main.py)."""
    raise HTTPException(status_code=503, detail="Reasoning orchestrator not initialized")


@router.post("/query", response_model=QueryResponse)
def query_kg(
    request: QueryRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Query provinces or districts, or execute raw Cypher queries."""
    start_time = time.time()
    
    try:
        # Handle raw Cypher queries
        if request.query:
            logger.info(f"Executing raw Cypher query: {request.query[:100]}...")
            data = db.execute_cypher(request.query)
            execution_time = (time.time() - start_time) * 1000
            return QueryResponse(
                data=data,
                execution_time=execution_time,
                provenance={
                    "query_type": "raw_cypher",
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )
        
        # Handle structured province/district queries
        if request.province:
            data = db.execute_cypher(
                """
                MATCH (p:Province {name:$name})-[:HAS_DISTRICT]->(d:District)
                RETURN p.name AS province, collect(d.name) AS districts ORDER BY province
                """, {"name": request.province}
            )
            if not data:
                raise HTTPException(status_code=404, detail="Province not found")
            execution_time = (time.time() - start_time) * 1000
            return QueryResponse(
                result=data[0],
                execution_time=execution_time,
                provenance={
                    "query_type": "province_districts",
                    "province": request.province,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )
            
        elif request.district:
            data = db.execute_cypher(
                """
                MATCH (d:District {name:$name})-[:IN_PROVINCE]->(p:Province)
                RETURN d.name AS district, p.name AS province
                """, {"name": request.district}
            )
            if not data:
                raise HTTPException(status_code=404, detail="District not found")
            execution_time = (time.time() - start_time) * 1000
            return QueryResponse(
                result=data[0],
                execution_time=execution_time,
                provenance={
                    "query_type": "district_province",
                    "district": request.district,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )
            
        else:
            # Default: list all provinces + district counts
            data = db.execute_cypher(
                """
                MATCH (p:Province)
                RETURN p.name AS province, p.districtCount AS districtCount
                ORDER BY province
                """
            )
            execution_time = (time.time() - start_time) * 1000
            return QueryResponse(
                result={"provinces": data},
                execution_time=execution_time,
                provenance={
                    "query_type": "all_provinces",
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/reason", response_model=ReasonResponse)
def reason_kg(
    request: ReasonRequest,
    orchestrator: ReasoningOrchestrator = Depends(get_reasoning_orchestrator)
):
    """Perform reasoning between provinces and districts, with optional constraints."""
    try:
        # If constraints provided, use constraint-based reasoning
        if request.constraints:
            logger.info(f"Constraint reasoning with: {request.constraints}")
            constraint_result = orchestrator.constraint_reason(request.constraints)
            return ReasonResponse(
                feasible=True,
                explanations=[constraint_result["explanation"]],
                result={"filtered_results": constraint_result["result"]},
                provenance={
                    "method": "constraint-based",
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )
        
        # Default: symbolic reasoning between province and district
        if not request.start_province or not request.target_district:
            raise HTTPException(
                status_code=400, 
                detail="Either provide constraints or both start_province and target_district"
            )

        logger.info(f"Symbolic reasoning from {request.start_province} to {request.target_district}")
        
        # Try symbolic reasoning first
        symbolic_result = orchestrator.symbolic_reason(
            request.start_province, 
            request.target_district
        )
        
        if symbolic_result.get("result"):
            return ReasonResponse(
                feasible=True,
                explanations=symbolic_result.get("explanation", []),
                result=symbolic_result.get("result"),
                provenance={
                    "method": "symbolic",
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )

        # No path found
        return ReasonResponse(
            feasible=False,
            explanations=symbolic_result.get("explanation", []),
            provenance={
                "method": "symbolic",
                "timestamp": datetime.datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reasoning failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reasoning failed: {str(e)}")


@router.post("/predict", response_model=PredictResponse)
def predict_similar(
    request: PredictRequest,
    orchestrator: ReasoningOrchestrator = Depends(get_reasoning_orchestrator)
):
    """Find similar nodes using vector similarity."""
    try:
        logger.info(f"Predicting similar entities for '{request.name}'")
        result = orchestrator.vector_reason_similar(request.name, top_k=request.top_k)
        return PredictResponse(
            result=result["result"],
            explanation=result["explanation"]
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/constraint_reason", response_model=ConstraintReasonResponse)
def constraint_reason_kg(
    request: ConstraintReasonRequest,
    orchestrator: ReasoningOrchestrator = Depends(get_reasoning_orchestrator)
):
    """Perform constraint-based reasoning for filtering provinces/districts."""
    try:
        logger.info(f"Constraint reasoning with: {request.constraints}")
        result = orchestrator.constraint_reason(request.constraints)
        return ConstraintReasonResponse(
            result=result["result"],
            explanation=result["explanation"]
        )
    except Exception as e:
        logger.error(f"Constraint reasoning failed: {e}")
        raise HTTPException(status_code=500, detail=f"Constraint reasoning failed: {str(e)}")


@router.post("/write", response_model=WriteResponse)
def write_kg(
    request: WriteRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Write/update nodes with provenance tracking."""
    try:
        logger.info(f"Writing {request.node_type} node: {request.properties}")
        
        # Basic validation
        allowed_types = ["Province", "District"]
        if request.node_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Node type must be one of {allowed_types}")
        
        # Ensure name is provided
        if "name" not in request.properties:
            raise HTTPException(status_code=400, detail="Node properties must include 'name'")
        
        # Create or merge node with provenance
        cypher = f"""
        MERGE (n:{request.node_type} {{name: $name}})
        ON CREATE SET n += $props, n.createdAt = datetime(), n.source = $source
        ON MATCH SET n += $props, n.updatedAt = datetime(), n.source = $source
        RETURN id(n) AS node_id
        """
        props = {k: v for k, v in request.properties.items() if k != "name"}
        params = {"name": request.properties["name"], "props": props, "source": request.source}
        
        result = db.execute_cypher(cypher, params)
        node_id = result[0]["node_id"] if result else None
        
        provenance = {
            "source": request.source,
            "timestamp": datetime.datetime.now().isoformat(),
            "operation": "write",
            "node_type": request.node_type
        }
        
        return WriteResponse(
            success=True,
            node_id=node_id,
            provenance=provenance
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Write failed: {e}")
        raise HTTPException(status_code=500, detail=f"Write failed: {str(e)}")


@router.get("/validate", response_model=ValidationResponse)
def validate_shacl(
    orchestrator: ReasoningOrchestrator = Depends(get_reasoning_orchestrator)
):
    """Run SHACL validation and return a summarized report."""
    try:
        logger.info("Running SHACL validation")
        result = orchestrator.shacl_validate()
        return ValidationResponse(
            conforms=result.get("conforms", False),
            violations=result.get("violations", [])
        )
    except Exception as e:
        logger.error(f"SHACL validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.get("/export", response_model=ExportResponse)
def export_data(db: DatabaseManager = Depends(get_db_manager)):
    """Export knowledge graph data."""
    try:
        logger.info("Exporting knowledge graph data")
        data = db.execute_cypher(
            """
            MATCH (p:Province)-[:HAS_DISTRICT]->(d:District)
            RETURN p.name AS province, collect(d.name) AS districts ORDER BY province
            """
        )
        return ExportResponse(turtle_like=data)
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/explain", response_model=ExplainResponse)
def explain_relationship(
    province: str,
    district: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get evidence path for province-district relationship."""
    try:
        logger.info(f"Explaining relationship between {province} and {district}")
        data = db.execute_cypher(
            """
            MATCH (p:Province {name:$p})-[r:HAS_DISTRICT]->(d:District {name:$d})
            RETURN p.name AS province, type(r) AS rel, d.name AS district
            """, {"p": province, "d": district}
        )
        
        if not data:
            raise HTTPException(
                status_code=404, 
                detail="No evidence path found between the specified province and district"
            )
            
        return ExplainResponse(evidence=data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Explanation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Explanation failed: {str(e)}")
