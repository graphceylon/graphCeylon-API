"""
Dependency injection functions for API routes.

This module breaks circular dependencies by providing a central place
for dependency injection that can be imported by all API modules.
"""

from fastapi import HTTPException
from typing import Optional
from neo4j import Driver

from database.manager import DatabaseManager
from services.reasoning.symbolic import ReasoningOrchestrator

# Global variables for dependency injection (set by main.py during startup)
_driver: Optional[Driver] = None
_db_manager: Optional[DatabaseManager] = None
_reasoning_orchestrator: Optional[ReasoningOrchestrator] = None


def set_driver(driver: Driver):
    """Set the Neo4j driver instance (called during app startup)."""
    global _driver
    _driver = driver


def set_db_manager(db_manager: DatabaseManager):
    """Set the database manager instance (called during app startup)."""
    global _db_manager
    _db_manager = db_manager


def set_reasoning_orchestrator(orchestrator: ReasoningOrchestrator):
    """Set the reasoning orchestrator instance (called during app startup)."""
    global _reasoning_orchestrator
    _reasoning_orchestrator = orchestrator


def get_driver() -> Driver:
    """Get the Neo4j driver instance."""
    if _driver is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return _driver


def get_db_manager() -> DatabaseManager:
    """Get the database manager instance."""
    if _db_manager is None:
        raise HTTPException(status_code=503, detail="Database manager not initialized")
    return _db_manager


def get_reasoning_orchestrator() -> ReasoningOrchestrator:
    """Get the reasoning orchestrator instance."""
    if _reasoning_orchestrator is None:
        raise HTTPException(status_code=503, detail="Reasoning orchestrator not initialized")
    return _reasoning_orchestrator
