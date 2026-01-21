"""Dependency injection utilities for the application."""

import logging
from typing import Optional
from neo4j import Driver, GraphDatabase
from fastapi import HTTPException

from .settings import settings


logger = logging.getLogger(__name__)

# Global instances for dependency injection
_driver: Optional[Driver] = None
_db_manager = None
_reasoning_orchestrator = None


def create_driver() -> Driver:
    """Create and return Neo4j driver instance.
    
    Returns:
        Neo4j driver instance
    """
    global _driver
    
    if _driver is None:
        logger.info(f"Creating Neo4j driver for {settings.neo4j_uri}")
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
    
    return _driver


def get_driver() -> Driver:
    """Get the Neo4j driver instance.
    
    Returns:
        Neo4j driver instance
        
    Raises:
        HTTPException: If driver is not initialized
    """
    if _driver is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return _driver


def set_db_manager(manager):
    """Set the database manager instance.
    
    Args:
        manager: DatabaseManager instance
    """
    global _db_manager
    _db_manager = manager


def get_db_manager():
    """Get the database manager instance.
    
    Returns:
        DatabaseManager instance
        
    Raises:
        HTTPException: If database manager is not initialized
    """
    if _db_manager is None:
        raise HTTPException(status_code=503, detail="Database manager not initialized")
    return _db_manager


def set_reasoning_orchestrator(orchestrator):
    """Set the reasoning orchestrator instance.
    
    Args:
        orchestrator: ReasoningOrchestrator instance
    """
    global _reasoning_orchestrator
    _reasoning_orchestrator = orchestrator


def get_reasoning_orchestrator():
    """Get the reasoning orchestrator instance.
    
    Returns:
        ReasoningOrchestrator instance
        
    Raises:
        HTTPException: If reasoning orchestrator is not initialized
    """
    if _reasoning_orchestrator is None:
        raise HTTPException(status_code=503, detail="Reasoning orchestrator not initialized")
    return _reasoning_orchestrator


def close_driver():
    """Close the Neo4j driver connection."""
    global _driver
    
    if _driver:
        logger.info("Closing Neo4j driver")
        _driver.close()
        _driver = None
