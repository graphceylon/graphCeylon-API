"""Main FastAPI application for the Sri Lanka Administrative Knowledge Graph."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.dependencies import create_driver
from database.manager import DatabaseManager
from services.reasoning.symbolic import ReasoningOrchestrator
from models.base import HealthResponse
from api import dependencies as api_deps

# --- Router imports (grouped by domain) ---
from api.routers.core import kg_operations, domains, semantic
from api.routers.tourism import attractions, holidays, hotels, news, projects, sub_attractions, events, restaurents, recommender
from api.routers.transport import railway_stations, train_schedules, bus_terminals, bus_schedules
from api.routers.intelligence import agent, ail_enhanced, graphrag, research, gnn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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
        logger.info("Starting up Knowledge Graph application...")
        driver = create_driver()
        db_manager = DatabaseManager(driver)
        reasoning_orchestrator = ReasoningOrchestrator(driver)

        # Set centralized dependencies for all routes
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
        logger.info("Shutting down Knowledge Graph application...")
        if driver:
            try:
                # Non-blocking close - driver will be cleaned up when process exits
                driver.close()
            except Exception:
                pass  # Ignore close errors on shutdown
        logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=settings.app_description,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register all routers ---

# Core KG operations
app.include_router(kg_operations.router)
app.include_router(domains.router)
app.include_router(semantic.router)

# Tourism entities
app.include_router(attractions.router)
app.include_router(sub_attractions.router)
app.include_router(restaurents.router)
app.include_router(events.router)
app.include_router(holidays.router)
app.include_router(hotels.router)
app.include_router(news.router)
app.include_router(projects.router)
app.include_router(recommender.router)

# Transport
app.include_router(railway_stations.router)
app.include_router(train_schedules.router)
app.include_router(bus_terminals.router)
app.include_router(bus_schedules.router)

# AI & Intelligence
app.include_router(agent.router)
app.include_router(ail_enhanced.router)
app.include_router(graphrag.router)
app.include_router(research.router)
app.include_router(gnn.router)


# --- App-level endpoints ---


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok", version=settings.app_version)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )
