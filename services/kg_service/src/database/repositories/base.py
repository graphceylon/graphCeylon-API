"""Base repository class for database operations."""

import logging
from typing import List, Dict, Any
from neo4j import Driver
from neo4j.time import DateTime, Date, Time


logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common database operations."""
    
    def __init__(self, driver: Driver):
        """Initialize repository with Neo4j driver.
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
    
    @staticmethod
    def _convert_neo4j_types(obj: Any) -> Any:
        """Convert Neo4j types to JSON-serializable types.
        
        Args:
            obj: Object to convert
            
        Returns:
            Converted object
        """
        if isinstance(obj, (DateTime, Date)):
            return obj.iso_format()
        elif isinstance(obj, Time):
            return obj.iso_format()
        elif isinstance(obj, dict):
            return {k: BaseRepository._convert_neo4j_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [BaseRepository._convert_neo4j_types(item) for item in obj]
        return obj
    
    def execute_query(self, cypher: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results.
        
        Args:
            cypher: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of result dictionaries
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher, parameters or {})
                data = [record.data() for record in result]
                return [self._convert_neo4j_types(record) for record in data]
        except Exception as e:
            logger.error(f"Failed to execute Cypher query: {e}")
            raise
    
    def execute_write(self, cypher: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a write transaction.
        
        Args:
            cypher: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of result dictionaries
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher, parameters or {})
                data = [record.data() for record in result]
                return [self._convert_neo4j_types(record) for record in data]
        except Exception as e:
            logger.error(f"Failed to execute write transaction: {e}")
            raise
    
    # Alias for backward compatibility
    def execute_cypher(self, cypher: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query (alias for execute_query).
        
        Args:
            cypher: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of result dictionaries
        """
        return self.execute_query(cypher, parameters)
