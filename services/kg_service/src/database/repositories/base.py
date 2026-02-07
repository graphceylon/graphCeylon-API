"""Base repository class for database operations with common utilities."""

import logging
from typing import List, Dict, Any
from pathlib import Path
from neo4j import Driver
from neo4j.time import DateTime, Date, Time

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common database operations and utilities.
    
    Provides:
    - Query execution with type conversion
    - File-based Cypher execution
    - Statistics gathering
    - Common repository patterns (load_schema, load_from_json)
    """
    
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
    
    def execute_cypher_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Execute Cypher commands from a file.
        
        Args:
            file_path: Path to the Cypher file
            
        Returns:
            List of result dictionaries from the last statement
        """
        try:
            logger.info(f"Executing Cypher file: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                cypher_content = f.read()
            
            # Split by semicolons and execute each statement
            statements = []
            for stmt in cypher_content.split(';'):
                # Remove comments and whitespace
                cleaned = '\n'.join(
                    line for line in stmt.split('\n')
                    if line.strip() and not line.strip().startswith('//')
                )
                if cleaned.strip():
                    statements.append(cleaned.strip())
            
            results = []
            with self.driver.session() as session:
                for statement in statements:
                    logger.debug(f"Executing statement: {statement[:100]}...")
                    result = session.run(statement)
                    data = [record.data() for record in result]
                    results.extend([self._convert_neo4j_types(record) for record in data])
            
            logger.info(f"Successfully executed {len(statements)} statements from file")
            return results
            
        except Exception as e:
            logger.error(f"Failed to execute Cypher file {file_path}: {e}")
            raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive database statistics.
        
        Returns:
            Dictionary with node counts, relationship counts, and breakdowns by type
        """
        try:
            # Get basic counts
            basic_query = """
            MATCH (n)
            WITH count(n) AS node_count
            MATCH ()-[r]->()
            RETURN node_count, count(r) AS relationship_count
            """
            
            basic_result = self.execute_query(basic_query)
            stats = basic_result[0] if basic_result else {"node_count": 0, "relationship_count": 0}
            
            # Get node labels count
            labels_query = """
            MATCH (n)
            UNWIND labels(n) AS label
            RETURN label, count(*) AS count
            ORDER BY count DESC
            """
            
            labels_result = self.execute_query(labels_query)
            stats["node_labels"] = {record["label"]: record["count"] for record in labels_result}
            
            # Get relationship types count
            rel_query = """
            MATCH ()-[r]->()
            RETURN type(r) AS type, count(r) AS count
            ORDER BY count DESC
            """
            
            rel_result = self.execute_query(rel_query)
            stats["relationship_types"] = {record["type"]: record["count"] for record in rel_result}
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            raise
    
    # ========== Helper Methods for Common Patterns ==========
    
    def _load_schema_from_file(self, schema_filename: str, entity_type: str) -> Dict[str, Any]:
        """Generic schema loading from file.
        
        Args:
            schema_filename: Name of schema file (e.g., 'init_attractions_schema.cypher')
            entity_type: Type of entity for logging (e.g., 'attractions')
            
        Returns:
            Dictionary with success status and message
        """
        try:
            from database.utils import DatabasePaths
            
            logger.info(f"Loading {entity_type} schema...")
            
            try:
                schema_path = DatabasePaths.resolve_schema_file(schema_filename)
            except FileNotFoundError:
                logger.warning(f"{entity_type} schema file not found, creating basic constraints")
                # Subclass can override this with specific constraints
                return {
                    "success": True,
                    "message": f"Basic {entity_type} constraints created (schema file not found)"
                }
            
            self.execute_cypher_file(str(schema_path))
            logger.info(f"{entity_type} schema loaded successfully")
            
            return {
                "success": True,
                "message": f"{entity_type} schema loaded"
            }
            
        except Exception as e:
            logger.error(f"Failed to load {entity_type} schema: {e}")
            raise
    
    def _check_apoc_available(self) -> bool:
        """Check if APOC plugin is available.
        
        Returns:
            True if APOC is available, False otherwise
        """
        try:
            from database.utils import check_apoc_available
            return check_apoc_available(self)
        except ImportError:
            # Fallback if utils not available
            try:
                result = self.execute_query("RETURN apoc.version() AS version")
                return bool(result and result[0].get('version'))
            except:
                return False
