
"""Main FastAPI application for the Sri Lanka Administrative Knowledge Graph."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase

from core.config import settings
from core.dependencies import create_driver
from database.manager import DatabaseManager
from services.reasoning import ReasoningOrchestrator
from models.schemas import (
    QueryRequest, ReasonRequest, PredictRequest,
    HealthResponse, QueryResponse, ReasonResponse, 
    PredictResponse, ValidationResponse, ExportResponse,
    ExplainResponse, StatisticsResponse, ErrorResponse,
    ConstraintReasonRequest, ConstraintReasonResponse, WriteRequest, WriteResponse
)
from api import dependencies as api_deps
from api import attractions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables for dependency injection
driver = None
db_manager = None
reasoning_orchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    global driver, db_manager, reasoning_orchestrator
    
    try:
        # Startup
        logger.info("Starting up Knowledge Graph application...")
        driver = create_driver()
        db_manager = DatabaseManager(driver)
        reasoning_orchestrator = ReasoningOrchestrator(driver)
        
        # Set dependencies for API routes
        api_deps.set_driver(driver)
        api_deps.set_db_manager(db_manager)
        api_deps.set_reasoning_orchestrator(reasoning_orchestrator)
        
        # Test database connection
        db_manager.execute_cypher("RETURN 1 AS test")
        logger.info("Database connection established successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down Knowledge Graph application...")
        if driver:
            driver.close()
        logger.info("Application shutdown complete")


# Create FastAPI app with lifespan management
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=settings.app_description,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
    ],  # React dev server (multiple ports for Vite)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers and override dependencies
app.include_router(attractions.router)
app.dependency_overrides[attractions.get_db_manager] = api_deps.get_db_manager

# Import and include domain router
from api import domains
app.include_router(domains.router)
app.dependency_overrides[domains.get_db_manager] = api_deps.get_db_manager

# Import and include holidays router
from api import holidays
app.include_router(holidays.router)
app.dependency_overrides[holidays.get_db_manager] = api_deps.get_db_manager

# Import and include projects router
from api import projects
app.include_router(projects.router)
app.dependency_overrides[projects.get_db_manager] = api_deps.get_db_manager

# Import and include news router
from api import news
app.include_router(news.router)
app.dependency_overrides[news.get_db_manager] = api_deps.get_db_manager

# Import and include semantic web router
from api import semantic
app.include_router(semantic.router)
app.dependency_overrides[semantic.get_db_manager] = api_deps.get_db_manager

# Import and include agent router
from api import agent
app.include_router(agent.router)
app.dependency_overrides[agent.get_reasoning_orchestrator] = api_deps.get_reasoning_orchestrator
app.dependency_overrides[agent.get_db_manager] = api_deps.get_db_manager

# Import and include Enhanced AIL router
from api import ail_enhanced
app.include_router(ail_enhanced.router)
app.dependency_overrides[ail_enhanced.get_db_manager] = api_deps.get_db_manager
app.dependency_overrides[ail_enhanced.get_driver] = api_deps.get_driver

# Import and include GraphRAG router
from api import graphrag
app.include_router(graphrag.router)
app.dependency_overrides[graphrag.get_db_manager] = api_deps.get_db_manager

# Import and include Research & AI router (GNN, Hybrid Reasoning)
from api import research
app.include_router(research.router)
app.dependency_overrides[research.get_driver] = api_deps.get_driver
app.dependency_overrides[research.get_db_manager] = api_deps.get_db_manager

# API Endpoints

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version=settings.app_version
    )


@app.post("/kg/initialize", response_model=dict)
def initialize_database(db: DatabaseManager = Depends(api_deps.get_db_manager)):
    """Initialize the database with ontology, shapes, and seed data."""
    try:
        logger.info("Database initialization requested")
        results = db.initialize_database()
        return {"message": "Database initialized successfully", "results": results}
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


@app.get("/kg/statistics", response_model=StatisticsResponse)
def get_statistics(db: DatabaseManager = Depends(api_deps.get_db_manager)):
    """Get database statistics."""
    try:
        stats = db.get_statistics()
        return StatisticsResponse(statistics=stats)
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@app.post("/kg/query", response_model=QueryResponse)
def query_kg(
    request: QueryRequest,
    db: DatabaseManager = Depends(api_deps.get_db_manager)
):
    """Query provinces or districts, or execute raw Cypher queries."""
    import time
    import datetime
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

@app.post("/kg/reason", response_model=ReasonResponse)
def reason_kg(
    request: ReasonRequest,
    orchestrator: ReasoningOrchestrator = Depends(api_deps.get_reasoning_orchestrator)
):
    """Perform reasoning between provinces and districts, with optional constraints."""
    try:
        import datetime
        
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

        # Predictive fallback if no path found
        predictive_result = orchestrator.predictive_reason_similar(
            request.target_district, 
            node_label="District", 
            top_k=5
        )
        
        return ReasonResponse(
            feasible=False,
            explanations=symbolic_result.get("explanation", []),
            predictive=predictive_result,
            provenance={
                "method": "symbolic+predictive",
                "timestamp": datetime.datetime.now().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reasoning failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reasoning failed: {str(e)}")


@app.post("/kg/predict", response_model=PredictResponse)
def predict_similar(
    request: PredictRequest,
    orchestrator: ReasoningOrchestrator = Depends(api_deps.get_reasoning_orchestrator)
):
    """Find similar nodes using lightweight similarity."""
    try:
        logger.info(f"Predicting similar entities for '{request.name}'")
        result = orchestrator.predictive_reason_similar(
            request.name, 
            node_label=request.label, 
            top_k=request.top_k
        )
        return PredictResponse(
            result=result["result"],
            explanation=result["explanation"]
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.get("/kg/validate", response_model=ValidationResponse)
def validate_shacl(
    orchestrator: ReasoningOrchestrator = Depends(api_deps.get_reasoning_orchestrator)
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


@app.get("/kg/export", response_model=ExportResponse)
def export_data(db: DatabaseManager = Depends(api_deps.get_db_manager)):
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


@app.get("/kg/explain", response_model=ExplainResponse)
def explain_relationship(
    province: str,
    district: str,
    db: DatabaseManager = Depends(api_deps.get_db_manager)
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


@app.post("/kg/constraint_reason", response_model=ConstraintReasonResponse)
def constraint_reason_kg(
    request: ConstraintReasonRequest,
    orchestrator: ReasoningOrchestrator = Depends(api_deps.get_reasoning_orchestrator)
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


@app.post("/kg/write", response_model=WriteResponse)
def write_kg(
    request: WriteRequest,
    db: DatabaseManager = Depends(api_deps.get_db_manager)
):
    """Write/update nodes with provenance tracking."""
    try:
        import datetime
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


@app.get("/kg/subscribe", response_model=dict)
def subscribe_updates():
    """Basic subscription endpoint for real-time updates (placeholder for WebSocket)."""
    # Note: Full WebSocket implementation would require additional setup
    return {
        "message": "Subscription endpoint active. Use WebSocket at /ws/updates for real-time notifications.",
        "status": "placeholder"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )
