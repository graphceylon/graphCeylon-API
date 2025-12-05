"""Vector index management for GraphRAG."""

import logging
from typing import Dict, Any
from neo4j import Driver

from core.config import settings
from services.graphrag.config import graphrag_config

logger = logging.getLogger(__name__)


class VectorIndexer:
    """Manages vector indexes for similarity search."""
    
    def __init__(self, driver: Driver):
        """Initialize vector indexer.
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
        self.index_name = graphrag_config.VECTOR_INDEX_NAME
    
    def ensure_index_exists(self) -> Dict[str, Any]:
        """Create vector index if it doesn't exist.
        
        Returns:
            Dictionary with success status and message
        """
        try:
            with self.driver.session() as session:
                # Check if index exists
                result = session.run(
                    "SHOW INDEXES WHERE name = $name",
                    {"name": self.index_name}
                )
                
                if result.single():
                    logger.info(f"Vector index '{self.index_name}' already exists")
                    return {"success": True, "message": "Index already exists"}
                
                # Create vector index
                session.run(f"""
                    CREATE VECTOR INDEX {self.index_name} IF NOT EXISTS
                    FOR (c:Chunk) ON (c.embedding)
                    OPTIONS {{indexConfig: {{
                        `vector.dimensions`: {settings.vector_dimensions},
                        `vector.similarity_function`: 'cosine'
                    }}}}
                """)
                
                logger.info(f"Vector index '{self.index_name}' created successfully")
                return {"success": True, "message": "Index created"}
                
        except Exception as e:
            logger.error(f"Failed to create vector index: {e}")
            raise
    
    def delete_index(self) -> Dict[str, Any]:
        """Delete the vector index.
        
        Returns:
            Dictionary with success status and message
        """
        try:
            with self.driver.session() as session:
                session.run(f"DROP INDEX {self.index_name} IF EXISTS")
                logger.info(f"Vector index '{self.index_name}' deleted")
                return {"success": True, "message": "Index deleted"}
        except Exception as e:
            logger.error(f"Failed to delete vector index: {e}")
            raise
    
    def get_index_info(self) -> Dict[str, Any]:
        """Get information about the vector index.
        
        Returns:
            Dictionary with index information
        """
        try:
            with self.driver.session() as session:
                result = session.run(
                    "SHOW INDEXES WHERE name = $name",
                    {"name": self.index_name}
                )
                record = result.single()
                
                if record:
                    return {
                        "exists": True,
                        "name": record.get("name"),
                        "type": record.get("type"),
                        "state": record.get("state"),
                        "populationPercent": record.get("populationPercent")
                    }
                else:
                    return {"exists": False}
        except Exception as e:
            logger.error(f"Failed to get index info: {e}")
            raise
