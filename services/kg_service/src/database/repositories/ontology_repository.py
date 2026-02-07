"""Repository for ontology and domain-related database operations."""

import logging
from typing import Dict, List, Any
from .base import BaseRepository
from core.config import settings
from ..utils import DatabasePaths

logger = logging.getLogger(__name__)


class OntologyRepository(BaseRepository):
    """Handle all ontology and domain structure-related database operations."""
    
    def initialize_database(self) -> Dict[str, Any]:
        """Initialize the database with constraints, ontology, and seed data."""
        results = {}
        
        try:
            logger.info("Starting database initialization...")
            
            # Step 1: Create n10s constraint
            logger.info("Creating n10s unique URI constraint...")
            self.execute_cypher(
                "CREATE CONSTRAINT n10s_unique_uri IF NOT EXISTS FOR (r:Resource) REQUIRE r.uri IS UNIQUE;"
            )
            results["constraint_created"] = True
            
            # Step 2: Initialize n10s graph configuration
            logger.info("Initializing n10s graph configuration...")
            try:
                self.execute_cypher(
                    "CALL n10s.graphconfig.init({handleVocabUris: 'SHORTEN', handleMultival: 'ARRAY', applyNeo4jNaming: true});"
                )
                results["graph_config"] = True
            except Exception as e:
                if "non-empty" in str(e):
                    logger.info("Graph is non-empty, skipping configuration initialization")
                    results["graph_config"] = "skipped (non-empty graph)"
                else:
                    raise
            
            # Step 3: Import ontology
            logger.info("Importing ontology...")
            ontology_path = DatabasePaths.get_project_root() / settings.ontology_file
            if not ontology_path.exists():
                raise FileNotFoundError(f"Ontology file not found: {ontology_path}")
            
            try:
                # Get path relative to neo4j/import/ to preserve subdirectory structure
                neo4j_import_dir = DatabasePaths.get_neo4j_import()
                ontology_relative = ontology_path.relative_to(neo4j_import_dir)
                self.execute_cypher(
                    f"CALL n10s.onto.import.fetch('file:///var/lib/neo4j/import/{ontology_relative.as_posix()}','Turtle');"
                )
                results["ontology_imported"] = True
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    logger.info("Ontology already imported, skipping")
                    results["ontology_imported"] = "skipped (already exists)"
                else:
                    raise
            
            # Step 4: Register namespace prefixes
            logger.info("Registering namespace prefixes...")
            try:
                self.execute_cypher(
                    "CALL n10s.nsprefixes.add('lk','http://example.org/lk#');"
                )
                results["prefixes_registered"] = True
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    logger.info("Namespace prefixes already registered, skipping")
                    results["prefixes_registered"] = "skipped (already exists)"
                else:
                    raise
            
            # Step 5: Import SHACL shapes
            logger.info("Importing SHACL shapes...")
            shapes_path = DatabasePaths.get_project_root() / settings.shapes_file
            if not shapes_path.exists():
                raise FileNotFoundError(f"Shapes file not found: {shapes_path}")
            
            try:
                # Get path relative to neo4j/import/ to preserve subdirectory structure
                neo4j_import_dir = DatabasePaths.get_neo4j_import()
                shapes_relative = shapes_path.relative_to(neo4j_import_dir)
                self.execute_cypher(
                    f"CALL n10s.validation.shacl.import.fetch('file:///var/lib/neo4j/import/{shapes_relative.as_posix()}','Turtle');"
                )
                results["shapes_imported"] = True
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    logger.info("SHACL shapes already imported, skipping")
                    results["shapes_imported"] = "skipped (already exists)"
                else:
                    raise
            
            # Step 6: Validate SHACL
            logger.info("Validating SHACL shapes...")
            violations = self.execute_cypher("CALL n10s.validation.shacl.validate() YIELD focusNode RETURN count(focusNode) AS violations;")
            results["validation"] = violations[0] if violations else {"violations": 0}
            
            # Step 7: Seed data
            logger.info("Seeding provinces and districts...")
            seed_path = DatabasePaths.get_project_root() / settings.seed_file
            if not seed_path.exists():
                raise FileNotFoundError(f"Seed file not found: {seed_path}")
            
            existing_provinces = self.execute_cypher("MATCH (p:Province) RETURN count(p) AS count;")
            existing_count = existing_provinces[0]["count"] if existing_provinces else 0
            
            if existing_count > 0:
                logger.info(f"Found {existing_count} existing provinces, skipping seed data")
                results["data_seeded"] = "skipped (data already exists)"
            else:
                self.execute_cypher_file(str(seed_path))
                results["data_seeded"] = True
            
            # Step 8: Sanity checks
            logger.info("Running sanity checks...")
            province_count = self.execute_cypher("MATCH (p:Province) RETURN count(p) AS count;")
            district_count = self.execute_cypher("MATCH (d:District) RETURN count(d) AS count;")
            
            results["sanity_check"] = {
                "provinces": province_count[0]["count"] if province_count else 0,
                "districts": district_count[0]["count"] if district_count else 0
            }
            
            logger.info("Database initialization completed successfully!")
            return results
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    def validate_shacl(self) -> Dict[str, Any]:
        """Validate SHACL shapes and return violation report."""
        try:
            violations = self.execute_cypher("CALL n10s.validation.shacl.validate();")
            return {
                "conforms": len(violations) == 0,
                "violations": violations,
                "violation_count": len(violations)
            }
        except Exception as e:
            logger.error(f"SHACL validation failed: {e}")
            raise
    
    def initialize_domain_structure(self) -> Dict[str, Any]:
        """Initialize the 12-domain architecture for Sri Lankan Tourism KG."""
        try:
            logger.info("Initializing domain-driven architecture...")
            domain_path = DatabasePaths.get_schema_file('init_domain_structure.cypher')
            
            if not domain_path.exists():
                raise FileNotFoundError(f"Domain structure file not found: {domain_path}")
            
            self.execute_cypher_file(str(domain_path))
            
            summary = self.execute_cypher("""
                MATCH (sl:Country {name: "Sri Lanka"})-[:HAS_DOMAIN]->(d:Domain)
                RETURN sl.name AS country,
                       count(d) AS total_domains,
                       collect({name: d.name, code: d.code, status: d.status, order: d.order}) AS domains
                ORDER BY sl.name
            """)
            
            logger.info("Domain structure initialized successfully")
            return {
                "success": True,
                "message": "Domain-driven architecture initialized",
                "summary": summary[0] if summary else {}
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize domain structure: {e}")
            raise
    
    def get_domain_overview(self) -> Dict[str, Any]:
        """Get an overview of all domains and their entity counts."""
        try:
            logger.info("Getting domain overview...")
            
            overview = self.execute_cypher("""
                MATCH (sl:Country {name: "Sri Lanka"})-[:HAS_DOMAIN]->(d:Domain)
                OPTIONAL MATCH (entity)-[:BELONGS_TO_DOMAIN]->(d)
                RETURN d.name AS domain,
                       d.code AS code,
                       d.order AS order,
                       d.status AS status,
                       d.description AS description,
                       d.examples AS examples,
                       count(DISTINCT entity) AS entity_count
                ORDER BY d.order
            """)
            
            return {
                "success": True,
                "total_domains": len(overview),
                "domains": overview
            }
            
        except Exception as e:
            logger.error(f"Failed to get domain overview: {e}")
            raise
    
    def get_domain_entities(self, domain_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all entities belonging to a specific domain."""
        try:
            logger.info(f"Getting entities for domain: {domain_name}")
            
            result = self.execute_cypher("""
                MATCH (d:Domain {name: $domain_name})
                MATCH (entity)-[:BELONGS_TO_DOMAIN]->(d)
                RETURN labels(entity) AS labels,
                       properties(entity) AS properties
                LIMIT $limit
            """, {"domain_name": domain_name, "limit": limit})
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get domain entities: {e}")
            raise
    
    def get_graph_structure(self) -> Dict[str, Any]:
        """Get the complete hierarchical structure of the knowledge graph."""
        try:
            logger.info("Getting graph structure...")
            
            structure = self.execute_cypher("""
                MATCH (sl:Country {name: "Sri Lanka"})
                OPTIONAL MATCH (sl)-[:HAS_DOMAIN]->(d:Domain)
                OPTIONAL MATCH (sl)-[:HAS_PROVINCE]->(p:Province)
                OPTIONAL MATCH (p)-[:HAS_DISTRICT]->(dist:District)
                WITH sl, 
                     count(DISTINCT d) AS domain_count,
                     count(DISTINCT p) AS province_count,
                     count(DISTINCT dist) AS district_count,
                     collect(DISTINCT {name: d.name, code: d.code, status: d.status}) AS domains,
                     collect(DISTINCT p.name) AS provinces
                OPTIONAL MATCH (a:Attraction)
                RETURN sl.name AS country,
                       domain_count,
                       province_count,
                       district_count,
                       count(DISTINCT a) AS attraction_count,
                       domains,
                       provinces
            """)
            
            return {
                "success": True,
                "structure": structure[0] if structure else {}
            }
            
        except Exception as e:
            logger.error(f"Failed to get graph structure: {e}")
            raise
    
    def cleanup_duplicate_relationships(self) -> Dict[str, Any]:
        """Remove duplicate relationships from the graph."""
        try:
            logger.info("Cleaning up duplicate relationships...")
            
            before = self.execute_cypher("""
                MATCH ()-[r]->()
                RETURN count(r) AS total_relationships
            """)
            before_count = before[0]['total_relationships'] if before else 0
            
            cleanup_path = DatabasePaths.get_neo4j_cleanup() / 'cleanup_duplicates.cypher'
            
            if not cleanup_path.exists():
                raise FileNotFoundError(f"Cleanup script not found: {cleanup_path}")
            
            self.execute_cypher_file(str(cleanup_path))
            
            after = self.execute_cypher("""
                MATCH ()-[r]->()
                RETURN count(r) AS total_relationships
            """)
            after_count = after[0]['total_relationships'] if after else 0
            
            summary = self.execute_cypher("""
                MATCH ()-[r]->()
                RETURN type(r) AS relationship_type, count(r) AS count
                ORDER BY relationship_type
            """)
            
            deleted = before_count - after_count
            
            logger.info(f"Duplicate relationships cleaned up: {deleted} duplicates removed")
            return {
                "success": True,
                "message": f"Removed {deleted} duplicate relationships",
                "before_count": before_count,
                "after_count": after_count,
                "deleted_count": deleted,
                "relationships_by_type": summary
            }
            
        except Exception as e:
            logger.error(f"Failed to cleanup duplicates: {e}")
            raise
