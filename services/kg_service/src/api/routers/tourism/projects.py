"""Tourism Projects API endpoints."""

import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List

from database.manager import DatabaseManager
from models.graph.knowledge_graph import WriteResponse
from models.domain.project import (
    ProjectQueryRequest,
    ProjectResponse,
    CreateProjectRequest
)
from api.dependencies import get_db_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Tourism Projects"])


@router.get("", response_model=ProjectResponse)
def get_all_projects(
    limit: int = 20,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get all tourism projects with optional limit."""
    try:
        logger.info(f"Getting all projects with limit={limit}")
        
        projects = db.query_projects({"limit": limit})
        
        return ProjectResponse(
            projects=projects,
            count=len(projects),
            query_info={"limit": limit}
        )
    except Exception as e:
        logger.error(f"Failed to get projects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get projects: {str(e)}")


@router.post("/query", response_model=ProjectResponse)
def query_projects(
    request: ProjectQueryRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """
    Query tourism projects with various filters.
    
    Filters:
    - title: Search by project title (case-insensitive)
    - province: Filter by province name
    - district: Filter by district name
    - project_type: Filter by project type
    - limit: Maximum number of results
    """
    try:
        filters = request.dict(exclude_none=True)
        logger.info(f"Querying projects with filters: {filters}")
        
        projects = db.query_projects(filters)
        
        return ProjectResponse(
            projects=projects,
            count=len(projects),
            query_info={
                "filters_applied": {k: v for k, v in filters.items() if k != "limit"},
                "limit": filters.get("limit", 20)
            }
        )
    except Exception as e:
        logger.error(f"Failed to query projects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query projects: {str(e)}")


@router.get("/types", response_model=Dict[str, Any])
def get_project_types(db: DatabaseManager = Depends(get_db_manager)):
    """Get all project types with counts."""
    try:
        logger.info("Getting project types")
        
        result = db.execute_cypher("""
            MATCH (p:TourismProject)
            WHERE p.project_type IS NOT NULL
            WITH p.project_type as type, count(p) as count
            ORDER BY count DESC
            RETURN type, count
        """)
        
        return {
            "types": result,
            "total_types": len(result)
        }
    except Exception as e:
        logger.error(f"Failed to get project types: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project types: {str(e)}")


@router.get("/provinces", response_model=Dict[str, Any])
def get_provinces_with_projects(db: DatabaseManager = Depends(get_db_manager)):
    """Get all provinces that have tourism projects."""
    try:
        logger.info("Getting provinces with projects")
        
        result = db.execute_cypher("""
            MATCH (p:Province)<-[:LOCATED_IN_PROVINCE]-(proj:TourismProject)
            WITH p, count(proj) as project_count
            ORDER BY p.name
            RETURN p.name as province, project_count
        """)
        
        return {
            "provinces": result,
            "count": len(result)
        }
    except Exception as e:
        logger.error(f"Failed to get provinces: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get provinces: {str(e)}")


@router.get("/districts", response_model=Dict[str, Any])
def get_districts_with_projects(db: DatabaseManager = Depends(get_db_manager)):
    """Get all districts that have tourism projects."""
    try:
        logger.info("Getting districts with projects")
        
        result = db.execute_cypher("""
            MATCH (d:District)<-[:LOCATED_IN_DISTRICT]-(proj:TourismProject)
            WITH d, count(proj) as project_count
            ORDER BY d.name
            RETURN d.name as district, project_count
        """)
        
        return {
            "districts": result,
            "count": len(result)
        }
    except Exception as e:
        logger.error(f"Failed to get districts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get districts: {str(e)}")


@router.post("/initialize", response_model=Dict[str, Any])
def initialize_projects(db: DatabaseManager = Depends(get_db_manager)):
    """Initialize tourism projects schema and load projects from JSON."""
    try:
        logger.info("Initializing tourism projects...")
        
        # Load schema
        schema_result = db.load_projects_schema()
        
        # Load projects data
        load_result = db.load_projects_from_json()
        
        return {
            "success": True,
            "schema": schema_result,
            "data": load_result,
            "message": "Tourism projects initialized successfully"
        }
    except Exception as e:
        logger.error(f"Failed to initialize projects: {e}")
        raise HTTPException(status_code=500, detail=f"Project initialization failed: {str(e)}")


@router.post("", response_model=WriteResponse)
def create_project(
    request: CreateProjectRequest,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Create a new tourism project."""
    try:
        logger.info(f"Creating project: {request.title}")
        
        result = db.create_project(request.dict(exclude_none=True))
        
        return WriteResponse(
            success=True,
            node_id=result.get("node_id"),
            provenance={
                "operation": "create_project",
                "source": "api",
                "timestamp": result.get("timestamp")
            }
        )
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


@router.get("/{project_id}", response_model=Dict[str, Any])
def get_project_by_id(
    project_id: str,
    db: DatabaseManager = Depends(get_db_manager)
):
    """Get a specific project by ID."""
    try:
        logger.info(f"Getting project by ID: {project_id}")
        
        result = db.execute_cypher("""
            MATCH (p:TourismProject)
            WHERE p.id = $id OR id(p) = toInteger($id)
            OPTIONAL MATCH (p)-[:LOCATED_IN_PROVINCE]->(prov:Province)
            OPTIONAL MATCH (p)-[:LOCATED_IN_DISTRICT]->(dist:District)
            RETURN p {
                .*,
                province: prov.name,
                district: dist.name
            } as project
        """, {"id": project_id})
        
        if not result:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return result[0]["project"]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")


@router.get("/statistics/overview", response_model=Dict[str, Any])
def get_project_statistics(db: DatabaseManager = Depends(get_db_manager)):
    """Get tourism project statistics."""
    try:
        logger.info("Getting project statistics")
        
        stats = db.get_project_statistics()
        
        return stats
    except Exception as e:
        logger.error(f"Failed to get project statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")
