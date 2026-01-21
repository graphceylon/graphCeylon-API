"""Unified database manager that delegates to specialized repositories."""

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
    BaseRepository
)
from services.embeddings import embedding_service
from core.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Unified manager that delegates to specialized repositories."""
    
    def __init__(self, driver: Driver):
        self.driver = driver
        self.base = BaseRepository(driver)
        self.attractions = AttractionRepository(driver)
        self.holidays = HolidayRepository(driver)
        self.projects = ProjectRepository(driver)
        self.news = NewsRepository(driver)
        self.ontology = OntologyRepository(driver)
        self.railway = RailwayRepository(driver)
    
    # Delegate common operations to base repository
    def execute_cypher(self, cypher: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        return self.base.execute_query(cypher, parameters)
    
    def execute_cypher_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Execute Cypher commands from a file."""
        return self.base.execute_cypher_file(file_path)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        return self.base.get_statistics()
    
    # Ontology & Initialization
    def initialize_database(self) -> Dict[str, Any]:
        """Initialize the database with constraints, ontology, and seed data."""
        results = self.ontology.initialize_database()
        
        # Also initialize vector index
        logger.info("Initializing vector index...")
        vector_results = self.create_vector_index()
        results["vector_index"] = vector_results
        
        return results
    
    def validate_shacl(self) -> Dict[str, Any]:
        """Validate SHACL shapes and return violation report."""
        try:
            return self.ontology.validate_shacl()
        except AttributeError:
            # If validate_shacl not implemented in ontology, return empty validation
            logger.warning("SHACL validation not implemented in ontology repository")
            return {
                "conforms": True,
                "violations": [],
                "violation_count": 0,
                "message": "SHACL validation not yet configured"
            }
        except Exception as e:
            logger.error(f"SHACL validation error: {e}")
            return {
                "conforms": False,
                "violations": [{"message": str(e)}],
                "violation_count": 1,
                "error": str(e)
            }
    
    def initialize_domain_structure(self) -> Dict[str, Any]:
        """Initialize the 12-domain architecture for Sri Lankan Tourism KG."""
        return self.ontology.initialize_domain_structure()
    
    def get_domain_overview(self) -> Dict[str, Any]:
        """Get an overview of all domains and their entity counts."""
        return self.ontology.get_domain_overview()
    
    def get_domain_entities(self, domain_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all entities belonging to a specific domain."""
        return self.ontology.get_domain_entities(domain_name, limit)
    
    def get_graph_structure(self) -> Dict[str, Any]:
        """Get the complete hierarchical structure of the knowledge graph."""
        return self.ontology.get_graph_structure()
    
    def cleanup_duplicate_relationships(self) -> Dict[str, Any]:
        """Remove duplicate relationships from the graph."""
        return self.ontology.cleanup_duplicate_relationships()
    
    # Vector Index Operations
    def create_vector_index(self) -> Dict[str, Any]:
        """Create a vector index for attractions."""
        try:
            logger.info(f"Creating vector index: {settings.vector_index_name}")
            
            check_query = "SHOW INDEXES WHERE name = $name"
            result = self.execute_cypher(check_query, {"name": settings.vector_index_name})
            
            if result:
                logger.info("Vector index already exists")
                return {"success": True, "message": "Index already exists"}
            
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

    def update_embeddings(self) -> Dict[str, Any]:
        """Update embeddings for attractions that don't have them."""
        try:
            logger.info("Updating attraction embeddings...")
            
            fetch_query = """
            MATCH (a:Attraction)
            WHERE a.embedding IS NULL AND a.description IS NOT NULL
            RETURN id(a) AS id, a.title AS title, a.description AS description
            LIMIT 100
            """
            
            records = self.execute_cypher(fetch_query)
            if not records:
                return {"success": True, "updated_count": 0, "message": "No attractions need embeddings"}
            
            logger.info(f"Found {len(records)} attractions to update")
            
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
                    self.execute_cypher(update_query, {"id": record["id"], "embedding": embedding})
                    updated_count += 1
            
            logger.info(f"Updated {updated_count} embeddings")
            return {"success": True, "updated_count": updated_count}
            
        except Exception as e:
            logger.error(f"Failed to update embeddings: {e}")
            return {"success": False, "error": str(e)}
    
    # Attraction Operations (delegate to AttractionRepository)
    def load_attractions_schema(self) -> Dict[str, Any]:
        """Load attraction schema (constraints and indexes)."""
        return self.attractions.load_schema()
    
    def cleanup_attractions(self) -> Dict[str, Any]:
        """Remove all attraction relationships to clean up messy graph."""
        return self.attractions.cleanup_relationships()
    
    def load_attractions_from_json(self, file_path: str = None) -> Dict[str, Any]:
        """Load attractions from JSON file using APOC and create relationships."""
        return self.attractions.load_from_json(file_path)
    
    def create_attraction(self, attraction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new attraction node."""
        return self.attractions.create_attraction(attraction_data)
    
    def link_attraction_to_district(self, attraction_title: str, district_name: str) -> Dict[str, Any]:
        """Link an attraction to a district and province."""
        return self.attractions.link_to_district(attraction_title, district_name)
    
    def query_attractions(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query attractions with various filters."""
        return self.attractions.query_attractions(filters)
    
    def get_attractions_by_district(self, district_name: str) -> List[Dict[str, Any]]:
        """Get all attractions in a specific district."""
        return self.attractions.get_by_district(district_name)
    
    def get_attractions_by_province(self, province_name: str) -> List[Dict[str, Any]]:
        """Get all attractions in a specific province (through districts)."""
        return self.attractions.get_by_province(province_name)
    
    # Holiday Operations (delegate to HolidayRepository)
    def initialize_temporal_structure(self) -> Dict[str, Any]:
        """Initialize the temporal structure (Year -> Month hierarchy)."""
        return self.holidays.initialize_temporal_structure()
    
    def load_holidays_from_json(self) -> Dict[str, Any]:
        """Load holidays from JSON file and connect to temporal structure."""
        return self.holidays.load_from_json()
    
    def query_holidays(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query holidays with various filters."""
        return self.holidays.query_holidays(filters)
    
    def get_holidays_by_year(self, year: int) -> List[Dict[str, Any]]:
        """Get all holidays for a specific year."""
        return self.holidays.get_by_year(year)
    
    def get_holidays_by_year_month(self, year: int, month: int) -> List[Dict[str, Any]]:
        """Get all holidays for a specific year and month."""
        return self.holidays.get_by_year_month(year, month)
    
    def get_holidays_by_category(self, category: str, year: int = None) -> List[Dict[str, Any]]:
        """Get holidays by category, optionally filtered by year."""
        return self.holidays.get_by_category(category, year)
    
    def get_holidays_by_type(self, holiday_type: str, year: int = None) -> List[Dict[str, Any]]:
        """Get holidays by type, optionally filtered by year."""
        return self.holidays.get_by_type(holiday_type, year)
    
    def get_public_holidays(self, year: int = None) -> List[Dict[str, Any]]:
        """Get all public holidays, optionally filtered by year."""
        return self.holidays.get_public_holidays(year)
    
    def get_temporal_structure(self) -> Dict[str, Any]:
        """Get the complete temporal structure with statistics."""
        return self.holidays.get_temporal_structure()
    
    def get_holiday_statistics(self) -> Dict[str, Any]:
        """Get comprehensive holiday statistics."""
        return self.holidays.get_statistics()
    
    def create_holiday(self, holiday_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new holiday and link to temporal structure."""
        return self.holidays.create(holiday_data)
    
    def get_upcoming_holidays(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get upcoming holidays from today."""
        return self.holidays.get_upcoming(limit)
    
    def search_holidays(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search holidays by name or description."""
        return self.holidays.search(query, limit)
    
    # Project Operations (delegate to ProjectRepository)
    def load_projects_schema(self) -> Dict[str, Any]:
        """Load tourism projects schema (constraints and indexes)."""
        return self.projects.load_schema()
    
    def load_projects_from_json(self) -> Dict[str, Any]:
        """Load tourism projects from JSON file."""
        return self.projects.load_from_json()
    
    def query_projects(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query tourism projects with various filters."""
        return self.projects.query(filters)
    
    def create_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new tourism project."""
        return self.projects.create(project_data)
    
    def get_project_statistics(self) -> Dict[str, Any]:
        """Get tourism project statistics."""
        return self.projects.get_statistics()
    
    # News Operations (delegate to NewsRepository)
    def load_news_schema(self) -> Dict[str, Any]:
        """Load tourism news schema (constraints and indexes)."""
        return self.news.load_schema()
    
    def load_news_from_json(self) -> Dict[str, Any]:
        """Load tourism news from JSON file."""
        return self.news.load_from_json()
    
    def query_news(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query news articles with various filters."""
        return self.news.query(filters)
    
    def create_news(self, news_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new news article."""
        return self.news.create(news_data)
    
    def get_news_statistics(self) -> Dict[str, Any]:
        """Get news article statistics."""
        return self.news.get_statistics()
    
    def get_latest_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get latest news articles."""
        return self.news.get_latest(limit)
    
    def search_news(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search news articles by title or content."""
        return self.news.search(query, limit)
