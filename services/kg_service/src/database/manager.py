"""Unified database manager providing access to specialized repositories.

This manager follows the Repository Pattern to provide clean separation of concerns.
Instead of exposing every repository method, it provides direct repository access,
making the API more maintainable and discoverable.
"""

import logging
from typing import Dict, List, Any
from neo4j import Driver

from .repositories import (
    AttractionRepository,
    HolidayRepository,
    ProjectRepository,
    NewsRepository,
    OntologyRepository,
    RailwayRepository,
    SubAttractionRepository,
    EventRepository,
    BusScheduleRepository,
    BaseRepository
)
from core.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Unified database manager with repository access.
    
    Provides:
    - Direct repository access via properties (e.g., db.attractions, db.holidays)
    - Common operations (execute_cypher, statistics)
    - Initialization and setup utilities
    - Vector index management
    
    Usage:
        db = DatabaseManager(driver)
        
        # Access repositories directly
        attractions = db.attractions.query_attractions({"province": "Western"})
        holidays = db.holidays.get_by_year(2026)
        
        # Use common operations
        results = db.execute_cypher("MATCH (n:Province) RETURN n")
        stats = db.get_statistics()
    """
    
    def __init__(self, driver: Driver):
        """Initialize database manager with Neo4j driver.
        
        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
        
        # Initialize base repository for common operations
        self._base = BaseRepository(driver)
        
        # Initialize specialized repositories
        self.attractions = AttractionRepository(driver)
        self.holidays = HolidayRepository(driver)
        self.projects = ProjectRepository(driver)
        self.news = NewsRepository(driver)
        self.ontology = OntologyRepository(driver)
        self.railway = RailwayRepository(driver)
        self.sub_attractions = SubAttractionRepository(driver)
        self.events = EventRepository(driver)
        self.bus_schedules = BusScheduleRepository(driver)
    
    # ========== Common Database Operations ==========
    
    def execute_cypher(self, cypher: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results.
        
        Args:
            cypher: Cypher query string
            parameters: Optional query parameters
            
        Returns:
            List of result dictionaries
        """
        return self._base.execute_query(cypher, parameters)
    
    def execute_cypher_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Execute Cypher commands from a file.
        
        Args:
            file_path: Path to Cypher file
            
        Returns:
            List of results from all statements
        """
        return self._base.execute_cypher_file(file_path)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive database statistics.
        
        Returns:
            Dictionary with node/relationship counts and breakdowns
        """
        return self._base.get_statistics()
    
    # ========== Initialization & Setup ==========
    
    def initialize_database(self) -> Dict[str, Any]:
        """Initialize database with ontology, schemas, and vector indexes.
        
        Performs:
        1. Creates n10s constraints and configuration
        2. Imports RDF ontology and SHACL shapes
        3. Seeds initial data (provinces, districts)
        4. Creates vector indexes for embeddings
        5. Validates installation
        
        Returns:
            Dictionary with initialization results and statistics
        """
        logger.info("Starting database initialization...")
        
        # Initialize ontology and seed data
        results = self.ontology.initialize_database()
        
        # Initialize vector index
        logger.info("Initializing vector index...")
        vector_results = self.create_vector_index()
        results["vector_index"] = vector_results
        
        logger.info("Database initialization complete")
        return results
    
    def validate_shacl(self) -> Dict[str, Any]:
        """Validate SHACL shapes and return violation report.
        
        Returns:
            Dictionary with conformance status and violations
        """
        try:
            return self.ontology.validate_shacl()
        except AttributeError:
            logger.warning("SHACL validation not implemented")
            return {
                "conforms": True,
                "violations": [],
                "violation_count": 0,
                "message": "SHACL validation not configured"
            }
        except Exception as e:
            logger.error(f"SHACL validation error: {e}")
            return {
                "conforms": False,
                "violations": [{"message": str(e)}],
                "violation_count": 1,
                "error": str(e)
            }
    
    # ========== Vector Operations ==========
    
    def create_vector_index(self) -> Dict[str, Any]:
        """Create vector index for semantic similarity search.
        
        Creates a cosine similarity index on attraction embeddings.
        
        Returns:
            Dictionary with success status and message
        """
        try:
            logger.info(f"Creating vector index: {settings.vector_index_name}")
            
            # Check if index already exists
            check_query = "SHOW INDEXES WHERE name = $name"
            result = self.execute_cypher(check_query, {"name": settings.vector_index_name})
            
            if result:
                logger.info("Vector index already exists")
                return {"success": True, "message": "Index already exists"}
            
            # Create vector index
            create_query = f"""
            CREATE VECTOR INDEX {settings.vector_index_name} IF NOT EXISTS
            FOR (n:Attraction) ON (n.embedding)
            OPTIONS {{indexConfig: {{
                `vector.dimensions`: {settings.vector_dimensions},
                `vector.similarity_function`: 'cosine'
            }}}}
            """
            self.execute_cypher(create_query)
            logger.info("Vector index created successfully")
            return {"success": True, "message": "Index created"}
            
        except Exception as e:
            logger.error(f"Failed to create vector index: {e}")
            return {"success": False, "error": str(e)}
    
    def update_embeddings(self, batch_size: int = 100) -> Dict[str, Any]:
        """Update embeddings for attractions missing them.
        
        Args:
            batch_size: Number of attractions to process per batch
            
        Returns:
            Dictionary with update statistics
        """
        try:
            from services.embeddings import embedding_service
            
            logger.info("Updating attraction embeddings...")
            
            # Find attractions without embeddings
            fetch_query = """
            MATCH (a:Attraction)
            WHERE a.embedding IS NULL AND a.description IS NOT NULL
            RETURN id(a) AS id, a.title AS title, a.description AS description
            LIMIT $batch_size
            """
            
            records = self.execute_cypher(fetch_query, {"batch_size": batch_size})
            
            if not records:
                return {
                    "success": True,
                    "updated_count": 0,
                    "message": "No attractions need embeddings"
                }
            
            logger.info(f"Found {len(records)} attractions to update")
            
            # Generate and update embeddings
            updated_count = 0
            for record in records:
                text = f"{record['title']}: {record['description']}"
                embedding = embedding_service.generate_embedding(text)
                
                if embedding:
                    update_query = """
                    MATCH (a:Attraction)
                    WHERE id(a) = $id
                    SET a.embedding = $embedding
                    """
                    self.execute_cypher(update_query, {
                        "id": record["id"],
                        "embedding": embedding
                    })
                    updated_count += 1
            
            logger.info(f"Updated {updated_count} embeddings")
            return {
                "success": True,
                "updated_count": updated_count,
                "total_processed": len(records)
            }
            
        except Exception as e:
            logger.error(f"Failed to update embeddings: {e}")
            return {"success": False, "error": str(e)}
    
    # ========== Backward Compatibility Methods ==========\n    # Legacy delegation methods for backward compatibility\n    # Prefer using repositories directly: db.attractions.query(), db.holidays.get_by_year(), etc.\n    \n    def query_attractions(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:\n        \"\"\"Query attractions (legacy method - prefer db.attractions.query_attractions()).\"\"\"\n        return self.attractions.query_attractions(filters)\n    \n    def query_holidays(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:\n        \"\"\"Query holidays (legacy method - prefer db.holidays.query_holidays()).\"\"\"\n        return self.holidays.query_holidays(filters)
