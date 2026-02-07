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
    """
    
    @staticmethod
    def get_project_root() -> Path:
        """Get the kg_service project root directory.
        
        Returns:
            Path to kg_service root directory
        """
        # From database/utils.py -> database -> src -> kg_service
        return Path(__file__).resolve().parent.parent.parent
    
    @staticmethod
    def get_neo4j_import() -> Path:
        """Get neo4j import directory path.
        
        Returns:
            Path to neo4j/import directory
        """
        return DatabasePaths.get_project_root() / "neo4j" / "import"
    
    @staticmethod
    def get_neo4j_scripts() -> Path:
        """Get neo4j scripts directory path.
        
        Returns:
            Path to neo4j/import/scripts directory
        """
        return DatabasePaths.get_neo4j_import() / "scripts"
    
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
