"""Database layer for Neo4j knowledge graph operations.

This module provides:
- DatabaseManager: Unified interface to all repository operations
- Repository pattern: Domain-specific data access via specialized repositories
- Type-safe operations with comprehensive error handling

Usage:
    from database.manager import DatabaseManager
    from core.dependencies import create_driver
    
    driver = create_driver()
    db = DatabaseManager(driver)
    
    # Access repositories directly
    attractions = db.attractions.query_attractions({"district": "Colombo"})
    holidays = db.holidays.get_by_year(2026)
    
    # Or use convenience methods
    results = db.execute_cypher("MATCH (n) RETURN n LIMIT 10")
    stats = db.get_statistics()
"""

from .manager import DatabaseManager

__all__ = ["DatabaseManager"]
