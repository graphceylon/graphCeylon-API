"""Repository for tourism project-related database operations."""

import logging
import datetime
from typing import Dict, List, Any
from .base import BaseRepository
from ..utils import DatabasePaths

logger = logging.getLogger(__name__)


class ProjectRepository(BaseRepository):
    """Handle all tourism project-related database operations."""
    
    def load_schema(self) -> Dict[str, Any]:
        """Load tourism projects schema (constraints and indexes)."""
        try:
            logger.info("Loading projects schema...")
            schema_path = DatabasePaths.get_schema_file('init_projects_schema.cypher')
            
            if not schema_path.exists():
                raise FileNotFoundError(f"Projects schema file not found: {schema_path}")
            
            self.execute_cypher_file(str(schema_path))
            
            logger.info("Projects schema loaded successfully")
            return {"success": True, "message": "Projects schema loaded"}
            
        except Exception as e:
            logger.error(f"Failed to load projects schema: {e}")
            raise
    
    def load_from_json(self) -> Dict[str, Any]:
        """Load tourism projects from JSON file."""
        try:
            logger.info("Loading projects from JSON...")

            # Refresh from GCS before APOC reads the file from Neo4j's import mount
            from core.gcs_downloader import refresh_sltda_projects
            refresh_sltda_projects(str(DatabasePaths.get_data_file('sltda_projects.json')))

            apoc_check = self.execute_cypher("RETURN apoc.version() AS version;")
            if not apoc_check:
                raise Exception("APOC plugin is not available. Please ensure it's installed.")
            
            logger.info(f"APOC version: {apoc_check[0].get('version', 'unknown')}")
            
            load_path = DatabasePaths.get_schema_file('load_projects.cypher')
            
            if not load_path.exists():
                raise FileNotFoundError(f"Projects load script not found: {load_path}")
            
            with open(load_path, 'r', encoding='utf-8') as file:
                cypher_content = file.read()
            
            cypher_content = cypher_content.replace("'file: ///", "'file:///")
            lines = cypher_content.split('\n')
            cleaned_lines = [line for line in lines if line.strip() and not line.strip().startswith('//')]
            cleaned_content = '\n'.join(cleaned_lines)
            
            statements = [stmt.strip() for stmt in cleaned_content.split(';') if stmt.strip()]
            
            logger.info(f"Found {len(statements)} statements to execute")
            
            for i, stmt in enumerate(statements):
                if stmt:
                    try:
                        result = self.execute_cypher(stmt)
                        if i < 3:
                            logger.debug(f"Statement {i+1} executed successfully")
                    except Exception as e:
                        logger.warning(f"Statement {i+1} execution warning: {e}")
                        continue
            
            stats = self.get_statistics()
            
            logger.info(f"Projects loaded successfully")
            return {
                "success": True,
                "message": "Projects loaded from JSON",
                "statistics": stats
            }
            
        except Exception as e:
            logger.error(f"Failed to load projects: {e}")
            raise
    
    def query(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query tourism projects with various filters."""
        try:
            logger.info(f"Querying projects with filters: {filters}")
            
            match_clause = "MATCH (p:TourismProject)"
            where_clauses = []
            params = {}
            
            if filters.get("title"):
                where_clauses.append("toLower(p.title) CONTAINS toLower($title)")
                params["title"] = filters["title"]
            
            if filters.get("project_type"):
                where_clauses.append("p.project_type = $project_type")
                params["project_type"] = filters["project_type"]
            
            if filters.get("province"):
                match_clause += "-[:LOCATED_IN_PROVINCE]->(prov:Province)"
                where_clauses.append("prov.name = $province")
                params["province"] = filters["province"]
            
            if filters.get("district"):
                match_clause += "-[:LOCATED_IN_DISTRICT]->(dist:District)"
                where_clauses.append("dist.name = $district")
                params["district"] = filters["district"]
            
            where_clause = ""
            if where_clauses:
                where_clause = "WHERE " + " AND ".join(where_clauses)
            
            return_clause = """
            OPTIONAL MATCH (p)-[:LOCATED_IN_PROVINCE]->(prov:Province)
            OPTIONAL MATCH (p)-[:LOCATED_IN_DISTRICT]->(dist:District)
            RETURN p {
                .*,
                id: id(p),
                province: prov.name,
                district: dist.name
            } as project
            ORDER BY p.title
            """
            
            limit = filters.get("limit", 20)
            params["limit"] = limit
            limit_clause = "LIMIT $limit"
            
            cypher = f"{match_clause} {where_clause} {return_clause} {limit_clause}"
            
            result = self.execute_cypher(cypher, params)
            projects = [r["project"] for r in result]
            
            return projects
            
        except Exception as e:
            logger.error(f"Failed to query projects: {e}")
            raise
    
    def create(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new tourism project."""
        try:
            logger.info(f"Creating project: {project_data.get('title')}")
            
            project_id = f"proj_{project_data['title'].lower().replace(' ', '_')}_{datetime.datetime.now().timestamp()}"
            
            cypher = """
            CREATE (p:TourismProject {
                id: $id,
                title: $title,
                image: $image,
                description: $description,
                details: $details,
                contact_text: $contact_text,
                href: $href,
                project_type: $project_type,
                created_at: datetime()
            })
            RETURN id(p) as node_id, p.id as project_id
            """
            
            params = {
                "id": project_id,
                "title": project_data["title"],
                "image": project_data.get("image"),
                "description": project_data.get("description"),
                "details": project_data.get("details", []),
                "contact_text": project_data.get("contact_text"),
                "href": project_data.get("href"),
                "project_type": project_data.get("project_type")
            }
            
            result = self.execute_cypher(cypher, params)
            
            if project_data.get("province"):
                self.execute_cypher("""
                    MATCH (p:TourismProject {id: $project_id})
                    MATCH (prov:Province {name: $province})
                    MERGE (p)-[:LOCATED_IN_PROVINCE]->(prov)
                """, {"project_id": project_id, "province": project_data["province"]})
            
            if project_data.get("district"):
                self.execute_cypher("""
                    MATCH (p:TourismProject {id: $project_id})
                    MATCH (dist:District {name: $district})
                    MERGE (p)-[:LOCATED_IN_DISTRICT]->(dist)
                """, {"project_id": project_id, "district": project_data["district"]})
            
            return {
                "success": True,
                "project_id": result[0]["project_id"] if result else project_id,
                "node_id": result[0]["node_id"] if result else None,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get tourism project statistics."""
        try:
            logger.info("Getting project statistics")
            
            total = self.execute_cypher("""
                MATCH (p:TourismProject)
                RETURN count(p) as total
            """)
            
            by_type = self.execute_cypher("""
                MATCH (p:TourismProject)
                WHERE p.project_type IS NOT NULL
                RETURN p.project_type as type, count(p) as count
                ORDER BY count DESC
            """)
            
            by_province = self.execute_cypher("""
                MATCH (p:TourismProject)-[:LOCATED_IN_PROVINCE]->(prov:Province)
                RETURN prov.name as province, count(p) as count
                ORDER BY count DESC
            """)
            
            by_district = self.execute_cypher("""
                MATCH (p:TourismProject)-[:LOCATED_IN_DISTRICT]->(dist:District)
                RETURN dist.name as district, count(p) as count
                ORDER BY count DESC
            """)
            
            return {
                "total_projects": total[0]["total"] if total else 0,
                "by_type": by_type,
                "by_province": by_province,
                "by_district": by_district
            }
            
        except Exception as e:
            logger.error(f"Failed to get project statistics: {e}")
            raise
