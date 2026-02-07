"""Domain architecture API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
import logging

from database.manager import DatabaseManager
from api.dependencies import get_db_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/domains", tags=["Domain Architecture"])


@router.post("/initialize", response_model=Dict[str, Any])
async def initialize_domains(db: DatabaseManager = Depends(get_db_manager)):
    """
    Initialize the 12-domain architecture for Sri Lankan Tourism Knowledge Graph.
    
    This creates:
    - Root Country node (Sri Lanka)
    - 12 Domain nodes with metadata
    - Relationships between country and domains
    - Links existing attractions to Destination & Attraction domain
    """
    try:
        result = db.initialize_domain_structure()
        return result
    except Exception as e:
        logger.error(f"Failed to initialize domains: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview", response_model=Dict[str, Any])
async def get_domain_overview(db: DatabaseManager = Depends(get_db_manager)):
    """
    Get an overview of all 12 domains with entity counts.
    
    Returns:
    - Domain name, code, order, status
    - Description and examples
    - Count of entities in each domain
    """
    try:
        result = db.get_domain_overview()
        return result
    except Exception as e:
        logger.error(f"Failed to get domain overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain_name}/entities", response_model=List[Dict[str, Any]])
async def get_domain_entities(
    domain_name: str,
    limit: int = 100,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Get all entities belonging to a specific domain.
    
    Parameters:
    - domain_name: Name of the domain (e.g., "Destination & Attraction")
    - limit: Maximum number of entities to return (default: 100)
    """
    try:
        result = db.get_domain_entities(domain_name, limit)
        return result
    except Exception as e:
        logger.error(f"Failed to get domain entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/structure", response_model=Dict[str, Any])
async def get_graph_structure(db: DatabaseManager = Depends(get_db_manager)):
    """
    Get the complete hierarchical structure of the knowledge graph.
    
    Returns:
    - Country information
    - Domain counts and details
    - Province and district counts
    - Attraction counts
    - Complete hierarchy
    """
    try:
        result = db.get_graph_structure()
        return result
    except Exception as e:
        logger.error(f"Failed to get graph structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup-duplicates", response_model=Dict[str, Any])
async def cleanup_duplicate_relationships(db: DatabaseManager = Depends(get_db_manager)):
    """
    Remove duplicate relationships from the knowledge graph.
    
    This removes:
    - Duplicate HAS_DOMAIN relationships
    - Duplicate HAS_PROVINCE relationships
    - Duplicate IN_COUNTRY relationships
    - Duplicate BELONGS_TO_DOMAIN relationships
    - Other duplicate relationships between nodes
    
    Returns a summary of remaining relationship counts.
    """
    try:
        result = db.cleanup_duplicate_relationships()
        return result
    except Exception as e:
        logger.error(f"Failed to cleanup duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))
