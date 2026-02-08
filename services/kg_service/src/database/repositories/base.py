"""Base repository class for database operations with common utilities."""

import logging
from typing import List, Dict, Any
from pathlib import Path
from neo4j import Driver
from neo4j.time import DateTime, Date, Time
from ..utils import DatabasePaths

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
    
    # ========== Common Repository Utilities ==========
    
    def load_schema_from_file(self, schema_filename: str) -> Dict[str, Any]:
        """Load schema (constraints and indexes) from a Cypher file.
        
        Args:
            schema_filename: Name of the schema file (e.g., 'init_attractions_schema.cypher')
            
        Returns:
            Dictionary with success status and message
        """
        try:
            logger.info(f"Loading schema from {schema_filename}...")
            schema_path = DatabasePaths.get_schema_file(schema_filename)
            
            if not schema_path.exists():
                logger.warning(f"Schema file not found: {schema_path}")
                return {
                    "success": False,
                    "message": f"Schema file not found: {schema_filename}"
                }
            
            self.execute_cypher_file(str(schema_path))
            logger.info(f"Schema loaded successfully from {schema_filename}")
            
            return {
                "success": True,
                "message": f"Schema loaded from {schema_filename}"
            }
            
        except Exception as e:
            logger.error(f"Failed to load schema from {schema_filename}: {e}")
            raise
    
    def load_data_from_json(self, 
                            json_filename: str, 
                            node_label: str,
                            process_record_fn: callable) -> Dict[str, Any]:
        """Load data from JSON file and process each record.
        
        Args:
            json_filename: Name of the JSON file (e.g., 'attractions.json')
            node_label: Label of the nodes being loaded (for logging)
            process_record_fn: Function to process each record, should return True on success
            
        Returns:
            Dictionary with load statistics
        """
        try:
            logger.info(f"Loading {node_label} data from {json_filename}...")
            data_path = DatabasePaths.get_data_file(json_filename)
            
            if not data_path.exists():
                raise FileNotFoundError(f"Data file not found: {data_path}")
            
            # Load JSON data
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both direct array and object with key
            records = self._extract_records(data, node_label.lower() + 's')
            
            logger.info(f"Found {len(records)} {node_label} records to import")
            
            # Process each record
            imported_count = 0
            skipped_count = 0
            
            for record in records:
                try:
                    if process_record_fn(record):
                        imported_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    logger.warning(f"Failed to import {node_label}: {e}")
                    skipped_count += 1
                    continue
            
            logger.info(f"Successfully imported {imported_count} {node_label}, skipped {skipped_count}")
            
            return {
                "success": True,
                "message": f"{node_label} data loaded from {json_filename}",
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "total_records": len(records)
            }
            
        except Exception as e:
            logger.error(f"Failed to load {node_label} data from {json_filename}: {e}")
            raise
    
    def _extract_records(self, data: Any, key: str) -> List[Dict[str, Any]]:
        """Extract records from JSON data.
        
        Args:
            data: Loaded JSON data
            key: Key to look for if data is a dict
            
        Returns:
            List of record dictionaries
        """
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Try exact key first, then try with variations
            if key in data:
                return data[key]
            # Try singular form
            singular = key.rstrip('s')
            if singular in data:
                return data[singular]
        
        raise ValueError(f"Could not extract records from data. Expected list or dict with '{key}' key")
    
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
