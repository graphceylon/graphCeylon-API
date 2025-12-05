"""API handlers for database management operations."""

import logging
from fastapi import APIRouter, HTTPException, Depends

from database.manager import DatabaseManager
from core.config import settings
from models.base import StatisticsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kg", tags=["Database Management"])


def get_db_manager() -> DatabaseManager:
    """Dependency to get database manager (will be overridden by main.py)."""
    raise HTTPException(status_code=503, detail="Database manager not initialized")


@router.post("/initialize", response_model=dict)
def initialize_database(db: DatabaseManager = Depends(get_db_manager)):
    """Initialize the database with ontology, shapes, and seed data."""
    try:
        logger.info("Database initialization requested")
        results = db.initialize_database()
        return {"message": "Database initialized successfully", "results": results}
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


@router.get("/statistics", response_model=StatisticsResponse)
def get_statistics(db: DatabaseManager = Depends(get_db_manager)):
    """Get database statistics."""
    try:
        stats = db.get_statistics()
        return StatisticsResponse(statistics=stats)
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.get("/subscribe", response_model=dict)
def subscribe_updates():
    """Basic subscription endpoint for real-time updates (placeholder for WebSocket)."""
    return {
        "message": "Subscription endpoint active. Use WebSocket at /ws/updates for real-time notifications.",
        "status": "placeholder"
    }
