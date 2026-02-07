"""Database utility functions and helpers.

Provides centralized utilities for:
- Path resolution (avoiding fragile parent.parent.parent chains)
- Common query patterns
- Error handling helpers
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DatabasePaths:
    """Centralized path management for database operations.
    
    Eliminates fragile Path(__file__).parent.parent chains by providing
    clean access to project directories.
    
    All paths are resolved once and cached for performance.
    """
    
    _project_root: Optional[Path] = None
    
    @classmethod
    def get_project_root(cls) -> Path:
        """Get the kg_service project root directory.
        
        Returns:
            Path to kg_service root directory
        """
        if cls._project_root is None:
            # From database/utils.py -> database -> src -> kg_service
            cls._project_root = Path(__file__).resolve().parent.parent.parent
        return cls._project_root
    
    @classmethod
    def get_neo4j_import(cls) -> Path:
        """Get neo4j import directory path.
        
        Returns:
            Path to neo4j/import directory
        """
        return cls.get_project_root() / "neo4j" / "import"
    
    @classmethod
    def get_neo4j_scripts(cls) -> Path:
        """Get neo4j scripts directory path.
        
        Returns:
            Path to neo4j/import/scripts directory
        """
        return cls.get_neo4j_import() / "scripts"
    
    @classmethod
    def get_neo4j_cleanup(cls) -> Path:
        """Get neo4j cleanup scripts directory path.
        
        Returns:
            Path to neo4j/import/cleanup directory
        """
        return cls.get_neo4j_import() / "cleanup"
    
    @classmethod
    def get_data_directory(cls) -> Path:
        """Get data directory path.
        
        Returns:
            Path to data/kg_service/data directory
        """
        # Go up to graphCeylon-API, then to data
        return cls.get_project_root().parent.parent / "data" / "kg_service" / "data"
    
    @classmethod
    def get_schema_file(cls, filename: str) -> Path:
        """Get full path to a schema file.
        
        Args:
            filename: Schema filename (e.g., 'init_attractions_schema.cypher')
            
        Returns:
            Full path to schema file
        """
        return cls.get_neo4j_scripts() / filename
    
    @classmethod
    def get_data_file(cls, filename: str) -> Path:
        """Get full path to a data file.
        
        Args:
            filename: Data filename (e.g., 'attractions.json')
            
        Returns:
            Full path to data file
        """
        return cls.get_data_directory() / filename
    
    @staticmethod
    def get_data_directory() -> Path:
        """Get data directory path.
        
        Returns:
            Path to data/kg_service/data directory
        """
        return DatabasePaths.get_project_root().parent.parent / "data" / "kg_service" / "data"
    
    @staticmethod
    def resolve_schema_file(filename: str) -> Path:
        """Resolve path to a schema file in neo4j/import/scripts.
        
        Args:
            filename: Name of the schema file
            
        Returns:
            Full path to schema file
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        path = DatabasePaths.get_neo4j_scripts() / filename
        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {path}")
        return path
    
    @staticmethod
    def resolve_data_file(filename: str) -> Path:
        """Resolve path to a data file in data directory.
        
        Args:
            filename: Name of the data file
            
        Returns:
            Full path to data file
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        path = DatabasePaths.get_data_directory() / filename
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")
        return path


def check_apoc_available(base_repo) -> bool:
    """Check if APOC plugin is available in Neo4j.
    
    Args:
        base_repo: BaseRepository instance to execute query
        
    Returns:
        True if APOC is available, False otherwise
    """
    try:
        result = base_repo.execute_query("RETURN apoc.version() AS version")
        if result and result[0].get('version'):
            logger.info(f"APOC version: {result[0]['version']}")
            return True
        return False
    except Exception as e:
        logger.warning(f"APOC not available: {e}")
        return False


def ensure_apoc_available(base_repo) -> None:
    """Ensure APOC plugin is available, raise exception if not.
    
    Args:
        base_repo: BaseRepository instance to execute query
        
    Raises:
        RuntimeError: If APOC is not available
    """
    if not check_apoc_available(base_repo):
        raise RuntimeError(
            "APOC plugin is not available. "
            "Please install APOC in Neo4j plugins directory."
        )
