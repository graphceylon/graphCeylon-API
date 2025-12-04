"""Database operations and initialization for Neo4j knowledge graph."""

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from neo4j import GraphDatabase, Driver
from neo4j.time import DateTime
from ..core.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages Neo4j database operations and initialization."""
    
    def __init__(self, driver: Driver):
        self.driver = driver
    
    @staticmethod
    def _convert_neo4j_types(obj: Any) -> Any:
        """Convert Neo4j types to JSON-serializable types."""
        if isinstance(obj, DateTime):
            return obj.iso_format()
        elif isinstance(obj, dict):
            return {k: DatabaseManager._convert_neo4j_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DatabaseManager._convert_neo4j_types(item) for item in obj]
        return obj
    
    def execute_cypher(self, cypher: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        try:
            with self.driver.session() as session:
                result = session.run(cypher, parameters or {})
                data = [record.data() for record in result]
                # Convert Neo4j types to JSON-serializable types
                return [self._convert_neo4j_types(record) for record in data]
        except Exception as e:
            logger.error(f"Failed to execute Cypher query: {e}")
            raise
    
    def execute_cypher_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Execute Cypher commands from a file, splitting by semicolons."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                cypher_content = file.read()
            
            # Split by semicolons and filter out comments and empty statements
            statements = []
            for stmt in cypher_content.split(';'):
                # Remove comments and whitespace
                cleaned = '\n'.join(
                    line for line in stmt.split('\n') 
                    if line.strip() and not line.strip().startswith('//')
                )
                if cleaned.strip():
                    statements.append(cleaned.strip())
            
            # Execute each statement separately
            results = []
            for stmt in statements:
                try:
                    result = self.execute_cypher(stmt)
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Statement execution warning: {e}")
                    continue
            
            return results
        except Exception as e:
            logger.error(f"Failed to execute Cypher file {file_path}: {e}")
            raise
    
    def create_vector_index(self) -> Dict[str, Any]:
        """Create a vector index for attractions."""
        try:
            logger.info(f"Creating vector index: {settings.vector_index_name}")
            
            # Check if index exists
            check_query = "SHOW INDEXES WHERE name = $name"
            result = self.execute_cypher(check_query, {"name": settings.vector_index_name})
            
            if result:
                logger.info("Vector index already exists")
                return {"success": True, "message": "Index already exists"}
            
            # Create index
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
            # Fallback for older Neo4j versions or different editions
            return {"success": False, "error": str(e)}

    def update_embeddings(self) -> Dict[str, Any]:
        """Update embeddings for attractions that don't have them."""
        try:
            from ..services.embeddings import embedding_service
            
            logger.info("Updating attraction embeddings...")
            
            # Fetch attractions without embeddings
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
            
            # Step 2: Initialize n10s graph configuration (skip if graph is non-empty)
            logger.info("Initializing n10s graph configuration...")
            try:
                self.execute_cypher(
                    "CALL n10s.graphconfig.init({handleVocabUris: 'SHORTEN', handleMultival: 'ARRAY', applyNeo4jNaming: true});"
                )
                results["graph_config"] = True
                logger.info("Graph configuration initialized successfully")
            except Exception as e:
                if "non-empty" in str(e):
                    logger.info("Graph is non-empty, skipping configuration initialization")
                    results["graph_config"] = "skipped (non-empty graph)"
                else:
                    raise
            
            # Step 3: Import ontology (skip if already imported)
            logger.info("Importing ontology...")
            ontology_path = Path(settings.ontology_file)
            if not ontology_path.exists():
                raise FileNotFoundError(f"Ontology file not found: {ontology_path}")
            
            try:
                # Use the relative path that maps to the container's /var/lib/neo4j/import directory
                ontology_filename = ontology_path.name
                self.execute_cypher(
                    f"CALL n10s.onto.import.fetch('file:///var/lib/neo4j/import/{ontology_filename}','Turtle');"
                )
                results["ontology_imported"] = True
                logger.info("Ontology imported successfully")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    logger.info("Ontology already imported, skipping")
                    results["ontology_imported"] = "skipped (already exists)"
                else:
                    raise
            
            # Step 4: Register namespace prefixes (skip if already exists)
            logger.info("Registering namespace prefixes...")
            try:
                self.execute_cypher(
                    "CALL n10s.nsprefixes.add('lk','http://example.org/lk#');"
                )
                results["prefixes_registered"] = True
                logger.info("Namespace prefixes registered successfully")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    logger.info("Namespace prefixes already registered, skipping")
                    results["prefixes_registered"] = "skipped (already exists)"
                else:
                    raise
            
            # Step 5: Import SHACL shapes (skip if already imported)
            logger.info("Importing SHACL shapes...")
            shapes_path = Path(settings.shapes_file)
            if not shapes_path.exists():
                raise FileNotFoundError(f"Shapes file not found: {shapes_path}")
            
            try:
                # Use the relative path that maps to the container's /var/lib/neo4j/import directory
                shapes_filename = shapes_path.name
                self.execute_cypher(
                    f"CALL n10s.validation.shacl.import.fetch('file:///var/lib/neo4j/import/{shapes_filename}','Turtle');"
                )
                results["shapes_imported"] = True
                logger.info("SHACL shapes imported successfully")
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
            
            # Step 7: Seed data (check if already exists)
            logger.info("Seeding provinces and districts...")
            seed_path = Path(settings.seed_file)
            if not seed_path.exists():
                raise FileNotFoundError(f"Seed file not found: {seed_path}")
            
            # Check if data already exists
            existing_provinces = self.execute_cypher("MATCH (p:Province) RETURN count(p) AS count;")
            existing_count = existing_provinces[0]["count"] if existing_provinces else 0
            
            if existing_count > 0:
                logger.info(f"Found {existing_count} existing provinces, skipping seed data")
                results["data_seeded"] = "skipped (data already exists)"
            else:
                self.execute_cypher_file(str(seed_path))
                results["data_seeded"] = True
                logger.info("Seed data imported successfully")
            
            # Step 8: Sanity checks
            logger.info("Running sanity checks...")
            province_count = self.execute_cypher("MATCH (p:Province) RETURN count(p) AS count;")
            district_count = self.execute_cypher("MATCH (d:District) RETURN count(d) AS count;")
            
            results["sanity_check"] = {
                "provinces": province_count[0]["count"] if province_count else 0,
                "districts": district_count[0]["count"] if district_count else 0
            }
            
            # Step 9: Initialize Vector Index
            logger.info("Initializing vector index...")
            vector_results = self.create_vector_index()
            results["vector_index"] = vector_results
            
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
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        try:
            stats = {}
            
            # Total counts
            node_result = self.execute_cypher("MATCH (n) RETURN count(n) AS count;")
            stats["node_count"] = node_result[0]["count"] if node_result else 0
            
            rel_result = self.execute_cypher("MATCH ()-[r]->() RETURN count(r) AS count;")
            stats["relationship_count"] = rel_result[0]["count"] if rel_result else 0
            
            # Count nodes by label
            label_result = self.execute_cypher(
                "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC;"
            )
            stats["node_labels"] = {item["label"]: item["count"] for item in label_result if item.get("label")}
            
            # Count relationships by type
            rel_type_result = self.execute_cypher(
                "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY count DESC;"
            )
            stats["relationship_types"] = {item["type"]: item["count"] for item in rel_type_result if item.get("type")}
            
            return stats
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            raise
    
    def load_attractions_schema(self) -> Dict[str, Any]:
        """Load attraction schema (constraints and indexes)."""
        try:
            logger.info("Loading attraction schema...")
            schema_path = Path(__file__).parent.parent.parent.parent / "neo4j" / "import" / "schemas" / "attractions_schema.cypher"
            
            if not schema_path.exists():
                raise FileNotFoundError(f"Attraction schema file not found: {schema_path}")
            
            self.execute_cypher_file(str(schema_path))
            logger.info("Attraction schema loaded successfully")
            return {"success": True, "message": "Attraction schema loaded"}
            
        except Exception as e:
            logger.error(f"Failed to load attraction schema: {e}")
            raise
    
    def cleanup_attractions(self) -> Dict[str, Any]:
        """Remove all attraction relationships to clean up messy graph."""
        try:
            logger.info("Cleaning up attraction relationships...")
            
            # Delete all relationships from attractions
            result = self.execute_cypher("MATCH (a:Attraction)-[r]-() DELETE r RETURN count(r) as deleted;")
            deleted_count = result[0].get('deleted', 0) if result else 0
            
            logger.info(f"Deleted {deleted_count} attraction relationships")
            return {"success": True, "deleted": deleted_count, "message": f"Deleted {deleted_count} relationships"}
            
        except Exception as e:
            logger.error(f"Failed to cleanup attractions: {e}")
            raise
    
    def load_attractions_from_json(self) -> Dict[str, Any]:
        """Load attractions from JSON file using APOC and create relationships."""
        try:
            logger.info("Loading attractions from JSON...")
            
            # Check if APOC is available
            apoc_check = self.execute_cypher("RETURN apoc.version() AS version;")
            if not apoc_check:
                raise Exception("APOC plugin is not available. Please ensure it's installed.")
            
            logger.info(f"APOC version: {apoc_check[0].get('version', 'unknown')}")
            
            # Load attractions using Cypher script
            load_path = Path(__file__).parent.parent.parent.parent / "neo4j" / "import" / "scripts" / "load_attractions.cypher"
            
            if not load_path.exists():
                raise FileNotFoundError(f"Attraction load script not found: {load_path}")
            
            # Read and execute the script
            with open(load_path, 'r', encoding='utf-8') as file:
                cypher_content = file.read()
            
            # Fix common formatting issues (remove extra spaces in file paths)
            original_content = cypher_content
            cypher_content = cypher_content.replace("'file: ///", "'file:///")
            # Note: File paths are now pre-configured to point to data/ subdirectory
            # No additional path replacements needed as scripts contain correct paths
            if original_content != cypher_content:
                logger.info("Fixed file path spacing in Cypher query")
            
            # Remove comment-only lines but keep inline comments
            lines = cypher_content.split('\n')
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                # Skip lines that are only comments
                if not stripped or stripped.startswith('//'):
                    continue
                cleaned_lines.append(line)
            
            cleaned_content = '\n'.join(cleaned_lines)
            
            # Split by semicolons and execute each statement separately
            statements = [stmt.strip() for stmt in cleaned_content.split(';') if stmt.strip()]
            
            logger.info(f"Found {len(statements)} statements to execute")
            
            results = []
            for i, stmt in enumerate(statements):
                if stmt:
                    try:
                        logger.info(f"Executing statement {i+1}/{len(statements)}...")
                        logger.debug(f"Statement preview: {stmt[:100]}...")
                        result = self.execute_cypher(stmt)
                        results.append(result)
                        logger.info(f"Statement {i+1} executed, result: {result}")
                    except Exception as e:
                        logger.error(f"Statement {i+1} execution error: {e}")
                        logger.error(f"Failed statement: {stmt[:200]}...")
                        raise
            
            # Count loaded attractions
            count_result = self.execute_cypher("MATCH (a:Attraction) RETURN count(a) AS count;")
            attraction_count = count_result[0]["count"] if count_result else 0
            
            # Also check what districts exist for debugging
            district_result = self.execute_cypher("MATCH (d:District) RETURN d.name AS name LIMIT 5;")
            logger.info(f"Sample districts in DB: {district_result}")
            
            logger.info(f"Total attractions in database: {attraction_count}")
            return {
                "success": True,
                "attractions_loaded": attraction_count,
                "message": f"Loaded {attraction_count} attractions"
            }
            
        except Exception as e:
            logger.error(f"Failed to load attractions: {e}")
            raise
    
    def create_attraction(self, attraction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new attraction node."""
        try:
            logger.info(f"Creating attraction: {attraction_data.get('title')}")
            
            cypher = """
            CREATE (a:Attraction {
                title: $title,
                description: $description,
                imageUrl: $image_url,
                latitude: $latitude,
                longitude: $longitude,
                googlePlaceId: $google_place_id,
                rating: $rating,
                createdAt: datetime()
            })
            RETURN id(a) AS node_id, a.title AS title
            """
            
            result = self.execute_cypher(cypher, {
                "title": attraction_data.get("title"),
                "description": attraction_data.get("description"),
                "image_url": attraction_data.get("image_url"),
                "latitude": attraction_data.get("latitude"),
                "longitude": attraction_data.get("longitude"),
                "google_place_id": attraction_data.get("google_place_id"),
                "rating": attraction_data.get("rating")
            })
            
            node_id = result[0]["node_id"] if result else None
            
            # Link to district if provided
            if attraction_data.get("district"):
                self.link_attraction_to_district(
                    attraction_data.get("title"),
                    attraction_data.get("district")
                )
            
            return {
                "success": True,
                "node_id": node_id,
                "title": attraction_data.get("title")
            }
            
        except Exception as e:
            logger.error(f"Failed to create attraction: {e}")
            raise
    
    def link_attraction_to_district(self, attraction_title: str, district_name: str) -> Dict[str, Any]:
        """Link an attraction to a district and province."""
        try:
            logger.info(f"Linking attraction '{attraction_title}' to district '{district_name}'")
            
            cypher = """
            MATCH (a:Attraction {title: $attraction_title})
            MATCH (d:District {name: $district_name})
            MERGE (a)-[:LOCATED_IN]->(d)
            MERGE (d)-[:HAS_ATTRACTION]->(a)
            
            WITH a, d
            MATCH (d)-[:IN_PROVINCE]->(p:Province)
            MERGE (a)-[:IN_PROVINCE]->(p)
            MERGE (p)-[:HAS_ATTRACTION]->(a)
            
            RETURN a.title AS attraction, d.name AS district, p.name AS province
            """
            
            result = self.execute_cypher(cypher, {
                "attraction_title": attraction_title,
                "district_name": district_name
            })
            
            return {
                "success": True,
                "result": result[0] if result else None
            }
            
        except Exception as e:
            logger.error(f"Failed to link attraction to district: {e}")
            raise
    
    def query_attractions(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query attractions with various filters."""
        try:
            logger.info(f"Querying attractions with filters: {filters}")
            
            # Build dynamic query
            match_clause = "MATCH (a:Attraction)"
            where_clauses = []
            params = {}
            
            # Add district filter
            if filters.get("district"):
                match_clause += "-[:LOCATED_IN]->(d:District {name: $district})"
                params["district"] = filters["district"]
            
            # Add province filter (query through district)
            if filters.get("province"):
                if not filters.get("district"):
                    match_clause += "-[:LOCATED_IN]->(d:District)"
                match_clause += "-[:IN_PROVINCE]->(p:Province {name: $province})"
                params["province"] = filters["province"]
            
            # Add title filter
            if filters.get("title"):
                where_clauses.append("toLower(a.title) CONTAINS toLower($title)")
                params["title"] = filters["title"]
            
            # Add coordinates filter
            if filters.get("has_coordinates") is not None:
                if filters["has_coordinates"]:
                    where_clauses.append("a.latitude IS NOT NULL AND a.longitude IS NOT NULL")
                else:
                    where_clauses.append("a.latitude IS NULL OR a.longitude IS NULL")
            
            # Build WHERE clause
            where_clause = ""
            if where_clauses:
                where_clause = " WHERE " + " AND ".join(where_clauses)
            
            # Build RETURN clause with district and province (through relationship)
            return_clause = """
            OPTIONAL MATCH (a)-[:LOCATED_IN]->(dist:District)
            OPTIONAL MATCH (dist)-[:IN_PROVINCE]->(prov:Province)
            RETURN a.title AS title,
                   a.description AS description,
                   a.imageUrl AS imageUrl,
                   a.latitude AS latitude,
                   a.longitude AS longitude,
                   a.coordinatesAccuracy AS coordinatesAccuracy,
                   a.googleMapsUrl AS googleMapsUrl,
                   a.googleMapsCoordinatesUrl AS googleMapsCoordinatesUrl,
                   a.googleMapsDirectionsUrl AS googleMapsDirectionsUrl,
                   a.googleMapsSatelliteUrl AS googleMapsSatelliteUrl,
                   a.googleEarthUrl AS googleEarthUrl,
                   a.googleStreetViewUrl AS googleStreetViewUrl,
                   a.coordinatesDecimal AS coordinatesDecimal,
                   a.coordinatesDms AS coordinatesDms,
                   a.appleMapsUrl AS appleMapsUrl,
                   a.googleMapsPlaceUrl AS googleMapsPlaceUrl,
                   a.formattedAddress AS formattedAddress,
                   a.country AS country,
                   a.countryCode AS countryCode,
                   a.city AS city,
                   a.town AS town,
                   a.village AS village,
                   a.postalCode AS postalCode,
                   a.route AS route,
                   a.streetNumber AS streetNumber,
                   a.geocodedAt AS geocodedAt,
                   a.geocodingService AS geocodingService,
                   a.geocodingConfidence AS geocodingConfidence,
                   a.googlePlaceId AS googlePlaceId,
                   a.rating AS rating,
                   a.userRatingsTotal AS userRatingsTotal,
                   a.website AS website,
                   a.phoneNumber AS phoneNumber,
                   a.priceLevel AS priceLevel,
                   a.placeTypes AS placeTypes,
                   a.placeUrl AS placeUrl,
                   a.editorialSummary AS editorialSummary,
                   a.placeName AS placeName,
                   a.icon AS icon,
                   a.vicinity AS vicinity,
                   a.links AS links,
                   a.reviews AS reviews,
                   a.photos AS photos,
                   a.openingHours AS openingHours,
                   a.scrapedAt AS scrapedAt,
                   dist.name AS district,
                   prov.name AS province
            ORDER BY a.title
            """
            
            limit = filters.get("limit", 10)
            full_query = f"{match_clause}{where_clause} {return_clause} LIMIT {limit}"
            
            result = self.execute_cypher(full_query, params)
            logger.info(f"Found {len(result)} attractions")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to query attractions: {e}")
            raise
    
    def get_attractions_by_district(self, district_name: str) -> List[Dict[str, Any]]:
        """Get all attractions in a specific district."""
        try:
            logger.info(f"Getting attractions for district: {district_name}")
            
            cypher = """
            MATCH (d:District {name: $district_name})<-[:LOCATED_IN]-(a:Attraction)
            RETURN a.title AS title,
                   a.description AS description,
                   a.imageUrl AS imageUrl,
                   a.latitude AS latitude,
                   a.longitude AS longitude,
                   a.coordinatesAccuracy AS coordinatesAccuracy,
                   a.googleMapsUrl AS googleMapsUrl,
                   a.formattedAddress AS formattedAddress,
                   a.googlePlaceId AS googlePlaceId,
                   a.rating AS rating,
                   a.userRatingsTotal AS userRatingsTotal,
                   a.website AS website,
                   a.phoneNumber AS phoneNumber,
                   a.priceLevel AS priceLevel,
                   a.placeTypes AS placeTypes,
                   a.placeUrl AS placeUrl,
                   a.editorialSummary AS editorialSummary,
                   a.vicinity AS vicinity,
                   a.links AS links,
                   a.openingHours AS openingHours
            ORDER BY a.title
            """
            
            result = self.execute_cypher(cypher, {"district_name": district_name})
            return result
            
        except Exception as e:
            logger.error(f"Failed to get attractions by district: {e}")
            raise
    
    def get_attractions_by_province(self, province_name: str) -> List[Dict[str, Any]]:
        """Get all attractions in a specific province (through districts)."""
        try:
            logger.info(f"Getting attractions for province: {province_name}")
            
            cypher = """
            MATCH (p:Province {name: $province_name})<-[:IN_PROVINCE]-(d:District)<-[:LOCATED_IN]-(a:Attraction)
            RETURN a.title AS title,
                   a.description AS description,
                   a.imageUrl AS imageUrl,
                   a.latitude AS latitude,
                   a.longitude AS longitude,
                   a.coordinatesAccuracy AS coordinatesAccuracy,
                   a.googleMapsUrl AS googleMapsUrl,
                   a.googleMapsPlaceUrl AS googleMapsPlaceUrl,
                   a.formattedAddress AS formattedAddress,
                   a.city AS city,
                   a.googlePlaceId AS googlePlaceId,
                   a.rating AS rating,
                   a.userRatingsTotal AS userRatingsTotal,
                   a.website AS website,
                   a.phoneNumber AS phoneNumber,
                   a.priceLevel AS priceLevel,
                   a.placeTypes AS placeTypes,
                   a.placeUrl AS placeUrl,
                   a.editorialSummary AS editorialSummary,
                   a.vicinity AS vicinity,
                   a.links AS links,
                   a.photos AS photos,
                   a.reviews AS reviews,
                   a.openingHours AS openingHours,
                   a.scrapedAt AS scrapedAt,
                   d.name AS district,
                   p.name AS province
            ORDER BY a.title
            """
            
            result = self.execute_cypher(cypher, {"province_name": province_name})
            return result
            
        except Exception as e:
            logger.error(f"Failed to get attractions by province: {e}")
            raise
    
    # =========================================================================
    # Domain-Driven Architecture Methods
    # =========================================================================
    
    def initialize_domain_structure(self) -> Dict[str, Any]:
        """Initialize the 12-domain architecture for Sri Lankan Tourism KG."""
        try:
            logger.info("Initializing domain-driven architecture...")
            domain_path = Path(__file__).parent.parent.parent.parent / "neo4j" / "import" / "scripts" / "init_domain_structure.cypher"
            
            if not domain_path.exists():
                raise FileNotFoundError(f"Domain structure file not found: {domain_path}")
            
            self.execute_cypher_file(str(domain_path))
            
            # Get summary
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
            
            # First, get count before cleanup
            before = self.execute_cypher("""
                MATCH ()-[r]->()
                RETURN count(r) AS total_relationships
            """)
            before_count = before[0]['total_relationships'] if before else 0
            
            cleanup_path = Path(__file__).parent.parent.parent.parent / "neo4j" / "import" / "cleanup" / "cleanup_duplicates.cypher"
            
            if not cleanup_path.exists():
                raise FileNotFoundError(f"Cleanup script not found: {cleanup_path}")
            
            self.execute_cypher_file(str(cleanup_path))
            
            # Get count after cleanup
            after = self.execute_cypher("""
                MATCH ()-[r]->()
                RETURN count(r) AS total_relationships
            """)
            after_count = after[0]['total_relationships'] if after else 0
            
            # Get summary by relationship type
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
    
    # =========================================================================
    # Temporal Domain & Holidays Methods
    # =========================================================================
    
    def initialize_temporal_structure(self) -> Dict[str, Any]:
        """Initialize the temporal structure (Year -> Month hierarchy)."""
        try:
            logger.info("Initializing temporal structure...")
            temporal_path = Path(__file__).parent.parent.parent.parent / "neo4j" / "import" / "scripts" / "init_temporal_structure.cypher"
            
            if not temporal_path.exists():
                raise FileNotFoundError(f"Temporal structure file not found: {temporal_path}")
            
            self.execute_cypher_file(str(temporal_path))
            
            # Get summary
            summary = self.execute_cypher("""
                MATCH (temporal:Domain { name: "Temporal" })-[:HAS_YEAR]->(y:Year)-[:HAS_MONTH]->(m:Month)
                WITH temporal, y, count(m) AS month_count
                RETURN temporal.name AS domain,
                       count(DISTINCT y) AS total_years,
                       collect({year: y.year, months: month_count, is_leap: y.is_leap_year, status: y.status}) AS years
            """)
            
            logger.info("Temporal structure initialized successfully")
            return {
                "success": True,
                "message": "Temporal structure initialized",
                "summary": summary[0] if summary else {}
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize temporal structure: {e}")
            raise
    
    def load_holidays_from_json(self) -> Dict[str, Any]:
        """Load holidays from JSON file and connect to temporal structure."""
        try:
            logger.info("Loading holidays from JSON...")
            
            # Check if APOC is available
            apoc_check = self.execute_cypher("RETURN apoc.version() AS version;")
            if not apoc_check:
                raise Exception("APOC plugin is not available. Please ensure it's installed.")
            
            logger.info(f"APOC version: {apoc_check[0].get('version', 'unknown')}")
            
            # Load holidays using Cypher script
            load_path = Path(__file__).parent.parent.parent.parent / "neo4j" / "import" / "scripts" / "load_holidays.cypher"
            
            if not load_path.exists():
                raise FileNotFoundError(f"Holiday load script not found: {load_path}")
            
            # Read and execute the script
            with open(load_path, 'r', encoding='utf-8') as file:
                cypher_content = file.read()
            
            # Fix common formatting issues (remove extra spaces in file paths)
            original_content = cypher_content
            cypher_content = cypher_content.replace("'file: ///", "'file:///")
            # Note: File paths are now pre-configured to point to data/ subdirectory
            # No additional path replacements needed as scripts contain correct paths
            if original_content != cypher_content:
                logger.info("Fixed file path spacing in Cypher query")
            
            # Remove comment-only lines but keep inline comments
            lines = cypher_content.split('\n')
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                # Skip lines that are only comments
                if not stripped or stripped.startswith('//'):
                    continue
                cleaned_lines.append(line)
            
            cleaned_content = '\n'.join(cleaned_lines)
            
            # Split by semicolons and execute each statement separately
            statements = [stmt.strip() for stmt in cleaned_content.split(';') if stmt.strip()]
            
            logger.info(f"Found {len(statements)} statements to execute")
            
            results = []
            for i, stmt in enumerate(statements):
                if stmt:
                    try:
                        logger.info(f"Executing statement {i+1}/{len(statements)}...")
                        logger.debug(f"Statement preview: {stmt[:100]}...")
                        result = self.execute_cypher(stmt)
                        results.append(result)
                        logger.info(f"Statement {i+1} executed, result: {result}")
                    except Exception as e:
                        # Check if this is a schema constraint/index error (safe to ignore)
                        error_str = str(e)
                        if "IndexWithNameAlreadyExists" in error_str or "ConstraintAlreadyExists" in error_str or "IndexOrConstraintAlreadyExists" in error_str:
                            logger.warning(f"Statement {i+1} execution warning: {e}")
                            logger.info(f"Skipping already existing constraint/index")
                            continue
                        else:
                            logger.error(f"Statement {i+1} execution error: {e}")
                            logger.error(f"Failed statement: {stmt[:200]}...")
                            raise
            
            # Get summary statistics
            stats = self.get_holiday_statistics()
            
            logger.info(f"Holidays loaded successfully")
            return {
                "success": True,
                "message": "Holidays loaded from JSON",
                "statistics": stats
            }
            
        except Exception as e:
            logger.error(f"Failed to load holidays: {e}")
            raise
    
    def query_holidays(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query holidays with various filters."""
        try:
            logger.info(f"Querying holidays with filters: {filters}")
            
            # Build dynamic query
            match_clause = "MATCH (h:Holiday)"
            where_clauses = []
            params = {}
            
            # Add year filter
            if filters.get("year"):
                where_clauses.append("h.year = $year")
                params["year"] = filters["year"]
            
            # Add month filter
            if filters.get("month"):
                where_clauses.append("h.month = $month")
                params["month"] = filters["month"]
            
            # Add category filter
            if filters.get("category"):
                where_clauses.append("h.category = $category")
                params["category"] = filters["category"]
            
            # Add holiday_type filter
            if filters.get("holiday_type"):
                where_clauses.append("h.holiday_type = $holiday_type")
                params["holiday_type"] = filters["holiday_type"]
            
            # Add is_public_holiday filter
            if filters.get("is_public_holiday") is not None:
                where_clauses.append("h.isPublicHoliday = $is_public_holiday")
                params["is_public_holiday"] = filters["is_public_holiday"]
            
            # Add name search filter
            if filters.get("name"):
                where_clauses.append("toLower(h.name) CONTAINS toLower($name)")
                params["name"] = filters["name"]
            
            # Build WHERE clause
            where_clause = ""
            if where_clauses:
                where_clause = " WHERE " + " AND ".join(where_clauses)
            
            # Build RETURN clause
            return_clause = """
            RETURN h.id AS id,
                   h.name AS name,
                   h.description AS description,
                   toString(h.start_date) AS start_date,
                   toString(h.end_date) AS end_date,
                   h.duration_days AS duration_days,
                   h.holiday_type AS holiday_type,
                   h.category AS category,
                   h.country AS country,
                   h.country_code AS country_code,
                   h.status AS status,
                   h.isPublicHoliday AS is_public_holiday,
                   h.location AS location,
                   h.year AS year,
                   h.month AS month,
                   h.day AS day,
                   h.weekday AS weekday,
                   h.calendar_link AS calendar_link
            ORDER BY h.start_date
            """
            
            limit = filters.get("limit", 50)
            full_query = f"{match_clause}{where_clause} {return_clause} LIMIT {limit}"
            
            result = self.execute_cypher(full_query, params)
            logger.info(f"Found {len(result)} holidays")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to query holidays: {e}")
            raise
    
    def get_holidays_by_year(self, year: int) -> List[Dict[str, Any]]:
        """Get all holidays for a specific year."""
        try:
            logger.info(f"Getting holidays for year: {year}")
            
            cypher = """
            MATCH (h:Holiday)-[:IN_YEAR]->(y:Year {year: $year})
            RETURN h.id AS id,
                   h.name AS name,
                   h.description AS description,
                   toString(h.start_date) AS start_date,
                   toString(h.end_date) AS end_date,
                   h.duration_days AS duration_days,
                   h.holiday_type AS holiday_type,
                   h.category AS category,
                   h.isPublicHoliday AS is_public_holiday,
                   h.year AS year,
                   h.month AS month,
                   h.day AS day,
                   h.weekday AS weekday
            ORDER BY h.start_date
            """
            
            result = self.execute_cypher(cypher, {"year": year})
            return result
            
        except Exception as e:
            logger.error(f"Failed to get holidays by year: {e}")
            raise
    
    def get_holidays_by_year_month(self, year: int, month: int) -> List[Dict[str, Any]]:
        """Get all holidays for a specific year and month."""
        try:
            logger.info(f"Getting holidays for {year}-{month}")
            
            cypher = """
            MATCH (h:Holiday)-[:IN_MONTH]->(m:Month {year: $year, month: $month})
            RETURN h.id AS id,
                   h.name AS name,
                   h.description AS description,
                   toString(h.start_date) AS start_date,
                   toString(h.end_date) AS end_date,
                   h.duration_days AS duration_days,
                   h.holiday_type AS holiday_type,
                   h.category AS category,
                   h.isPublicHoliday AS is_public_holiday,
                   h.year AS year,
                   h.month AS month,
                   h.day AS day,
                   h.weekday AS weekday
            ORDER BY h.day
            """
            
            result = self.execute_cypher(cypher, {"year": year, "month": month})
            return result
            
        except Exception as e:
            logger.error(f"Failed to get holidays by year/month: {e}")
            raise
    
    def get_holidays_by_category(self, category: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get holidays by category, optionally filtered by year."""
        try:
            logger.info(f"Getting holidays by category: {category}, year: {year}")
            
            if year:
                cypher = """
                MATCH (h:Holiday {category: $category, year: $year})
                """
            else:
                cypher = """
                MATCH (h:Holiday {category: $category})
                """
            
            cypher += """
            RETURN h.id AS id,
                   h.name AS name,
                   h.description AS description,
                   toString(h.start_date) AS start_date,
                   h.holiday_type AS holiday_type,
                   h.category AS category,
                   h.isPublicHoliday AS is_public_holiday,
                   h.year AS year,
                   h.month AS month,
                   h.day AS day
            ORDER BY h.start_date
            """
            
            params = {"category": category}
            if year:
                params["year"] = year
            
            result = self.execute_cypher(cypher, params)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get holidays by category: {e}")
            raise
    
    def get_holidays_by_type(self, holiday_type: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get holidays by type, optionally filtered by year."""
        try:
            logger.info(f"Getting holidays by type: {holiday_type}, year: {year}")
            
            if year:
                cypher = """
                MATCH (h:Holiday {holiday_type: $holiday_type, year: $year})
                """
            else:
                cypher = """
                MATCH (h:Holiday {holiday_type: $holiday_type})
                """
            
            cypher += """
            RETURN h.id AS id,
                   h.name AS name,
                   h.description AS description,
                   toString(h.start_date) AS start_date,
                   h.holiday_type AS holiday_type,
                   h.category AS category,
                   h.isPublicHoliday AS is_public_holiday,
                   h.year AS year,
                   h.month AS month,
                   h.day AS day
            ORDER BY h.start_date
            """
            
            params = {"holiday_type": holiday_type}
            if year:
                params["year"] = year
            
            result = self.execute_cypher(cypher, params)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get holidays by type: {e}")
            raise
    
    def get_public_holidays(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all public holidays, optionally filtered by year."""
        try:
            logger.info(f"Getting public holidays, year: {year}")
            
            if year:
                cypher = """
                MATCH (h:Holiday {isPublicHoliday: true, year: $year})
                """
                params = {"year": year}
            else:
                cypher = """
                MATCH (h:Holiday {isPublicHoliday: true})
                """
                params = {}
            
            cypher += """
            RETURN h.id AS id,
                   h.name AS name,
                   h.description AS description,
                   toString(h.start_date) AS start_date,
                   h.holiday_type AS holiday_type,
                   h.category AS category,
                   h.year AS year,
                   h.month AS month,
                   h.day AS day,
                   h.weekday AS weekday
            ORDER BY h.start_date
            """
            
            result = self.execute_cypher(cypher, params)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get public holidays: {e}")
            raise
    
    def get_temporal_structure(self) -> Dict[str, Any]:
        """Get the complete temporal structure with statistics."""
        try:
            logger.info("Getting temporal structure...")
            
            structure = self.execute_cypher("""
                MATCH (temporal:Domain {name: "Temporal"})-[:HAS_YEAR]->(y:Year)
                OPTIONAL MATCH (y)-[:HAS_MONTH]->(m:Month)
                OPTIONAL MATCH (y)-[:HAS_HOLIDAY]->(h:Holiday)
                WITH temporal, y, 
                     count(DISTINCT m) AS month_count,
                     count(DISTINCT h) AS holiday_count
                RETURN temporal.name AS domain,
                       temporal.code AS domain_code,
                       temporal.status AS domain_status,
                       collect({
                           year: y.year,
                           name: y.name,
                           type: y.type,
                           is_leap_year: y.is_leap_year,
                           status: y.status,
                           month_count: month_count,
                           holiday_count: holiday_count
                       }) AS years
            """)
            
            # Get overall summary
            summary = self.execute_cypher("""
                MATCH (h:Holiday)
                WITH count(h) AS total_holidays
                MATCH (y:Year)
                WITH total_holidays, count(y) AS total_years
                MATCH (m:Month)
                RETURN total_holidays,
                       total_years,
                       count(m) AS total_months
            """)
            
            return {
                "structure": structure[0] if structure else {},
                "summary": summary[0] if summary else {}
            }
            
        except Exception as e:
            logger.error(f"Failed to get temporal structure: {e}")
            raise
    
    def get_holiday_statistics(self) -> Dict[str, Any]:
        """Get comprehensive holiday statistics."""
        try:
            logger.info("Getting holiday statistics...")
            
            # Total count
            total = self.execute_cypher("MATCH (h:Holiday) RETURN count(h) AS total;")
            
            # Count by year
            by_year = self.execute_cypher("""
                MATCH (h:Holiday)
                RETURN h.year AS year, count(h) AS count
                ORDER BY year
            """)
            
            # Count by category
            by_category = self.execute_cypher("""
                MATCH (h:Holiday)
                RETURN h.category AS category, count(h) AS count
                ORDER BY category
            """)
            
            # Count by type
            by_type = self.execute_cypher("""
                MATCH (h:Holiday)
                RETURN h.holiday_type AS holiday_type, count(h) AS count
                ORDER BY count DESC
            """)
            
            # Count by month (across all years)
            by_month = self.execute_cypher("""
                MATCH (h:Holiday)
                RETURN h.month AS month, count(h) AS count
                ORDER BY month
            """)
            
            # Public holidays count
            public = self.execute_cypher("""
                MATCH (h:Holiday {isPublicHoliday: true})
                RETURN count(h) AS count
            """)
            
            return {
                "total_holidays": total[0]["total"] if total else 0,
                "public_holidays": public[0]["count"] if public else 0,
                "by_year": by_year,
                "by_category": by_category,
                "by_type": by_type,
                "by_month": by_month
            }
            
        except Exception as e:
            logger.error(f"Failed to get holiday statistics: {e}")
            raise
    
    def create_holiday(self, holiday_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new holiday and link to temporal structure."""
        try:
            from datetime import datetime
            
            logger.info(f"Creating holiday: {holiday_data.get('name')}")
            
            # Parse date to extract year, month, day
            start_date = datetime.strptime(holiday_data["start_date"], "%Y-%m-%d")
            end_date = datetime.strptime(holiday_data["end_date"], "%Y-%m-%d")
            year = start_date.year
            month = start_date.month
            day = start_date.day
            weekday = start_date.strftime("%A")
            duration = (end_date - start_date).days + 1
            
            # Generate ID
            holiday_id = f"{start_date.strftime('%Y%m%d')}_{holiday_data['name'].lower().replace(' ', '_')}"
            
            cypher = """
            CREATE (h:Holiday {
                id: $id,
                name: $name,
                description: $description,
                start_date: date($start_date),
                end_date: date($end_date),
                duration_days: $duration_days,
                holiday_type: $holiday_type,
                category: $category,
                country: "Sri Lanka",
                country_code: "LK",
                status: "confirmed",
                isPublicHoliday: $is_public_holiday,
                location: $location,
                year: $year,
                month: $month,
                day: $day,
                weekday: $weekday,
                created_at: datetime()
            })
            
            WITH h
            MATCH (m:Month {year: $year, month: $month})
            MERGE (h)-[:IN_MONTH]->(m)
            MERGE (m)-[:HAS_HOLIDAY]->(h)
            
            RETURN id(h) AS node_id, h.id AS holiday_id, h.name AS name
            """
            
            result = self.execute_cypher(cypher, {
                "id": holiday_id,
                "name": holiday_data["name"],
                "description": holiday_data.get("description"),
                "start_date": holiday_data["start_date"],
                "end_date": holiday_data["end_date"],
                "duration_days": duration,
                "holiday_type": holiday_data["holiday_type"],
                "category": holiday_data["category"],
                "is_public_holiday": holiday_data.get("is_public_holiday", True),
                "location": holiday_data.get("location"),
                "year": year,
                "month": month,
                "day": day,
                "weekday": weekday
            })
            
            return {
                "success": True,
                "holiday_id": result[0]["holiday_id"] if result else holiday_id,
                "node_id": result[0]["node_id"] if result else None,
                "name": holiday_data["name"]
            }
            
        except Exception as e:
            logger.error(f"Failed to create holiday: {e}")
            raise
    
    def get_upcoming_holidays(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get upcoming holidays from today."""
        try:
            logger.info(f"Getting upcoming {limit} holidays")
            
            cypher = """
            MATCH (h:Holiday)
            WHERE h.start_date >= date()
            RETURN h.id AS id,
                   h.name AS name,
                   h.description AS description,
                   toString(h.start_date) AS start_date,
                   h.holiday_type AS holiday_type,
                   h.category AS category,
                   h.isPublicHoliday AS is_public_holiday,
                   h.year AS year,
                   h.month AS month,
                   h.day AS day,
                   h.weekday AS weekday
            ORDER BY h.start_date
            LIMIT $limit
            """
            
            result = self.execute_cypher(cypher, {"limit": limit})
            return result
            
        except Exception as e:
            logger.error(f"Failed to get upcoming holidays: {e}")
            raise
    
    def search_holidays(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search holidays by name or description."""
        try:
            logger.info(f"Searching holidays with query: {query}")
            
            cypher = """
            MATCH (h:Holiday)
            WHERE toLower(h.name) CONTAINS toLower($query)
               OR toLower(h.description) CONTAINS toLower($query)
            RETURN h.id AS id,
                   h.name AS name,
                   h.description AS description,
                   toString(h.start_date) AS start_date,
                   h.holiday_type AS holiday_type,
                   h.category AS category,
                   h.isPublicHoliday AS is_public_holiday,
                   h.year AS year,
                   h.month AS month,
                   h.day AS day
            ORDER BY h.start_date
            LIMIT $limit
            """
            
            result = self.execute_cypher(cypher, {"query": query, "limit": limit})
            return result
            
        except Exception as e:
            logger.error(f"Failed to search holidays: {e}")
            raise
    
    # =========================================================================
    # Tourism Projects Methods
    # =========================================================================
    
    def load_projects_schema(self) -> Dict[str, Any]:
        """Load tourism projects schema (constraints and indexes)."""
        try:
            logger.info("Loading projects schema...")
            schema_path = Path(__file__).parent.parent.parent.parent / "neo4j" / "import" / "scripts" / "init_projects_schema.cypher"
            
            if not schema_path.exists():
                raise FileNotFoundError(f"Projects schema file not found: {schema_path}")
            
            self.execute_cypher_file(str(schema_path))
            
            logger.info("Projects schema loaded successfully")
            return {
                "success": True,
                "message": "Projects schema loaded"
            }
            
        except Exception as e:
            logger.error(f"Failed to load projects schema: {e}")
            raise
    
    def load_projects_from_json(self) -> Dict[str, Any]:
        """Load tourism projects from JSON file."""
        try:
            logger.info("Loading projects from JSON...")
            
            # Check if APOC is available
            apoc_check = self.execute_cypher("RETURN apoc.version() AS version;")
            if not apoc_check:
                raise Exception("APOC plugin is not available. Please ensure it's installed.")
            
            logger.info(f"APOC version: {apoc_check[0].get('version', 'unknown')}")
            
            # Load projects using Cypher script
            load_path = Path(__file__).parent.parent.parent.parent / "neo4j" / "import" / "scripts" / "load_projects.cypher"
            
            if not load_path.exists():
                raise FileNotFoundError(f"Projects load script not found: {load_path}")
            
            # Read and execute the script
            with open(load_path, 'r', encoding='utf-8') as file:
                cypher_content = file.read()
            
            # Fix common formatting issues (remove extra spaces in file paths)
            original_content = cypher_content
            cypher_content = cypher_content.replace("'file: ///", "'file:///")
            if original_content != cypher_content:
                logger.info("Fixed file path spacing in Cypher query")
            
            # Remove comment-only lines but keep inline comments
            lines = cypher_content.split('\n')
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                # Skip lines that are only comments
                if not stripped or stripped.startswith('//'):
                    continue
                cleaned_lines.append(line)
            
            cleaned_content = '\n'.join(cleaned_lines)
            
            # Split by semicolons and execute each statement separately
            statements = [stmt.strip() for stmt in cleaned_content.split(';') if stmt.strip()]
            
            logger.info(f"Found {len(statements)} statements to execute")
            
            results = []
            for i, stmt in enumerate(statements):
                if stmt:
                    try:
                        result = self.execute_cypher(stmt)
                        results.append(result)
                        if i < 3:  # Log first few for debugging
                            logger.debug(f"Statement {i+1} executed successfully")
                    except Exception as e:
                        logger.warning(f"Statement {i+1} execution warning: {e}")
                        continue
            
            # Get summary statistics
            stats = self.get_project_statistics()
            
            logger.info(f"Projects loaded successfully")
            return {
                "success": True,
                "message": "Projects loaded from JSON",
                "statistics": stats
            }
            
        except Exception as e:
            logger.error(f"Failed to load projects: {e}")
            raise
    
    def query_projects(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query tourism projects with various filters."""
        try:
            logger.info(f"Querying projects with filters: {filters}")
            
            # Build dynamic query
            match_clause = "MATCH (p:TourismProject)"
            where_clauses = []
            params = {}
            
            # Add title filter
            if filters.get("title"):
                where_clauses.append("toLower(p.title) CONTAINS toLower($title)")
                params["title"] = filters["title"]
            
            # Add project_type filter
            if filters.get("project_type"):
                where_clauses.append("p.project_type = $project_type")
                params["project_type"] = filters["project_type"]
            
            # Add province filter
            if filters.get("province"):
                match_clause += "-[:LOCATED_IN_PROVINCE]->(prov:Province)"
                where_clauses.append("prov.name = $province")
                params["province"] = filters["province"]
            
            # Add district filter
            if filters.get("district"):
                match_clause += "-[:LOCATED_IN_DISTRICT]->(dist:District)"
                where_clauses.append("dist.name = $district")
                params["district"] = filters["district"]
            
            # Build where clause
            where_clause = ""
            if where_clauses:
                where_clause = "WHERE " + " AND ".join(where_clauses)
            
            # Build return clause
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
            
            # Add limit
            limit = filters.get("limit", 20)
            params["limit"] = limit
            limit_clause = "LIMIT $limit"
            
            # Combine query
            cypher = f"{match_clause} {where_clause} {return_clause} {limit_clause}"
            
            logger.debug(f"Executing query: {cypher}")
            logger.debug(f"With params: {params}")
            
            result = self.execute_cypher(cypher, params)
            projects = [r["project"] for r in result]
            
            return projects
            
        except Exception as e:
            logger.error(f"Failed to query projects: {e}")
            raise
    
    def create_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new tourism project."""
        try:
            import datetime
            logger.info(f"Creating project: {project_data.get('title')}")
            
            # Generate unique ID
            project_id = f"proj_{project_data['title'].lower().replace(' ', '_')}_{datetime.datetime.now().timestamp()}"
            
            # Create project node
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
            
            # Link to province if provided
            if project_data.get("province"):
                self.execute_cypher("""
                    MATCH (p:TourismProject {id: $project_id})
                    MATCH (prov:Province {name: $province})
                    MERGE (p)-[:LOCATED_IN_PROVINCE]->(prov)
                """, {"project_id": project_id, "province": project_data["province"]})
            
            # Link to district if provided
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
    
    def get_project_statistics(self) -> Dict[str, Any]:
        """Get tourism project statistics."""
        try:
            logger.info("Getting project statistics")
            
            # Total projects
            total = self.execute_cypher("""
                MATCH (p:TourismProject)
                RETURN count(p) as total
            """)
            
            # By type
            by_type = self.execute_cypher("""
                MATCH (p:TourismProject)
                WHERE p.project_type IS NOT NULL
                RETURN p.project_type as type, count(p) as count
                ORDER BY count DESC
            """)
            
            # By province
            by_province = self.execute_cypher("""
                MATCH (p:TourismProject)-[:LOCATED_IN_PROVINCE]->(prov:Province)
                RETURN prov.name as province, count(p) as count
                ORDER BY count DESC
            """)
            
            # By district
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
    
    # =========================================================================
    # Tourism News Methods
    # =========================================================================
    
    def load_news_schema(self) -> Dict[str, Any]:
        """Load tourism news schema (constraints and indexes)."""
        try:
            logger.info("Loading news schema...")
            schema_path = Path(__file__).parent.parent.parent.parent / "neo4j" / "import" / "scripts" / "init_news_schema.cypher"
            
            if not schema_path.exists():
                raise FileNotFoundError(f"News schema file not found: {schema_path}")
            
            self.execute_cypher_file(str(schema_path))
            
            logger.info("News schema loaded successfully")
            return {
                "success": True,
                "message": "News schema loaded"
            }
            
        except Exception as e:
            logger.error(f"Failed to load news schema: {e}")
            raise
    
    def load_news_from_json(self) -> Dict[str, Any]:
        """Load tourism news from JSON file."""
        try:
            logger.info("Loading news from JSON...")
            
            # Check if APOC is available
            apoc_check = self.execute_cypher("RETURN apoc.version() AS version;")
            if not apoc_check:
                raise Exception("APOC plugin is not available. Please ensure it's installed.")
            
            logger.info(f"APOC version: {apoc_check[0].get('version', 'unknown')}")
            
            # Load news using Cypher script
            load_path = Path(__file__).parent.parent.parent.parent / "neo4j" / "import" / "scripts" / "load_news.cypher"
            
            if not load_path.exists():
                raise FileNotFoundError(f"News load script not found: {load_path}")
            
            # Read and execute the script
            with open(load_path, 'r', encoding='utf-8') as file:
                cypher_content = file.read()
            
            # Fix common formatting issues (remove extra spaces in file paths)
            original_content = cypher_content
            cypher_content = cypher_content.replace("'file: ///", "'file:///")
            if original_content != cypher_content:
                logger.info("Fixed file path spacing in Cypher query")
            
            # Remove comment-only lines but keep inline comments
            lines = cypher_content.split('\n')
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                # Skip lines that are only comments
                if not stripped or stripped.startswith('//'):
                    continue
                cleaned_lines.append(line)
            
            cleaned_content = '\n'.join(cleaned_lines)
            
            # Split by semicolons and execute each statement separately
            statements = [stmt.strip() for stmt in cleaned_content.split(';') if stmt.strip()]
            
            logger.info(f"Found {len(statements)} statements to execute")
            
            results = []
            for i, stmt in enumerate(statements):
                if stmt:
                    try:
                        result = self.execute_cypher(stmt)
                        results.append(result)
                        if i < 3:  # Log first few for debugging
                            logger.debug(f"Statement {i+1} executed successfully")
                    except Exception as e:
                        logger.warning(f"Statement {i+1} execution warning: {e}")
                        continue
            
            # Get summary statistics
            stats = self.get_news_statistics()
            
            logger.info(f"News loaded successfully")
            return {
                "success": True,
                "message": "News loaded from JSON",
                "statistics": stats
            }
            
        except Exception as e:
            logger.error(f"Failed to load news: {e}")
            raise
    
    def query_news(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query news articles with various filters."""
        try:
            logger.info(f"Querying news with filters: {filters}")
            
            # Build dynamic query
            match_clause = "MATCH (n:NewsArticle)"
            where_clauses = []
            params = {}
            
            # Add title filter
            if filters.get("title"):
                where_clauses.append("toLower(n.title) CONTAINS toLower($title)")
                params["title"] = filters["title"]
            
            # Add category filter
            if filters.get("category"):
                where_clauses.append("n.category = $category")
                params["category"] = filters["category"]
            
            # Add year filter
            if filters.get("year"):
                where_clauses.append("n.year = $year")
                params["year"] = filters["year"]
            
            # Add month filter
            if filters.get("month"):
                where_clauses.append("n.month = $month")
                params["month"] = filters["month"]
            
            # Add date range filters
            if filters.get("date_from"):
                where_clauses.append("n.date >= date($date_from)")
                params["date_from"] = filters["date_from"]
            
            if filters.get("date_to"):
                where_clauses.append("n.date <= date($date_to)")
                params["date_to"] = filters["date_to"]
            
            # Build where clause
            where_clause = ""
            if where_clauses:
                where_clause = "WHERE " + " AND ".join(where_clauses)
            
            # Build return clause
            return_clause = """
            RETURN n {
                .*,
                id: id(n),
                date: toString(n.date)
            } as article
            ORDER BY n.date DESC
            """
            
            # Add limit
            limit = filters.get("limit", 20)
            params["limit"] = limit
            limit_clause = "LIMIT $limit"
            
            # Combine query
            cypher = f"{match_clause} {where_clause} {return_clause} {limit_clause}"
            
            logger.debug(f"Executing query: {cypher}")
            logger.debug(f"With params: {params}")
            
            result = self.execute_cypher(cypher, params)
            articles = [r["article"] for r in result]
            
            return articles
            
        except Exception as e:
            logger.error(f"Failed to query news: {e}")
            raise
    
    def create_news(self, news_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new news article."""
        try:
            import datetime
            logger.info(f"Creating news article: {news_data.get('title')}")
            
            # Generate unique ID
            article_id = f"news_{news_data['title'].lower().replace(' ', '_')[:50]}_{datetime.datetime.now().timestamp()}"
            
            # Parse date if provided
            date_obj = None
            year, month, day = None, None, None
            if news_data.get("date"):
                try:
                    date_obj = datetime.datetime.strptime(news_data["date"], "%Y-%m-%d")
                    year = date_obj.year
                    month = date_obj.month
                    day = date_obj.day
                except:
                    logger.warning(f"Invalid date format: {news_data['date']}")
            
            # Create news article node
            cypher = """
            CREATE (n:NewsArticle {
                id: $id,
                title: $title,
                date: CASE WHEN $date IS NOT NULL THEN date($date) ELSE NULL END,
                image_url: $image_url,
                content: $content,
                read_more_url: $read_more_url,
                category: $category,
                tags: $tags,
                year: $year,
                month: $month,
                day: $day,
                created_at: datetime()
            })
            RETURN id(n) as node_id, n.id as article_id
            """
            
            params = {
                "id": article_id,
                "title": news_data["title"],
                "date": news_data.get("date"),
                "image_url": news_data.get("image_url"),
                "content": news_data.get("content"),
                "read_more_url": news_data.get("read_more_url"),
                "category": news_data.get("category"),
                "tags": news_data.get("tags", []),
                "year": year,
                "month": month,
                "day": day
            }
            
            result = self.execute_cypher(cypher, params)
            
            # Link to year and month if date is provided
            if year:
                self.execute_cypher("""
                    MATCH (n:NewsArticle {id: $article_id})
                    MERGE (y:Year {year: $year})
                    MERGE (n)-[:PUBLISHED_IN_YEAR]->(y)
                """, {"article_id": article_id, "year": year})
                
                if month:
                    self.execute_cypher("""
                        MATCH (n:NewsArticle {id: $article_id})
                        MATCH (y:Year {year: $year})
                        MERGE (m:Month {month: $month, year: $year})
                        MERGE (n)-[:PUBLISHED_IN_MONTH]->(m)
                        MERGE (y)-[:HAS_MONTH]->(m)
                    """, {"article_id": article_id, "year": year, "month": month})
            
            return {
                "success": True,
                "article_id": result[0]["article_id"] if result else article_id,
                "node_id": result[0]["node_id"] if result else None,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to create news article: {e}")
            raise
    
    def get_news_statistics(self) -> Dict[str, Any]:
        """Get news statistics."""
        try:
            logger.info("Getting news statistics")
            
            # Total articles
            total = self.execute_cypher("""
                MATCH (n:NewsArticle)
                RETURN count(n) as total
            """)
            
            # By year
            by_year = self.execute_cypher("""
                MATCH (n:NewsArticle)
                WHERE n.year IS NOT NULL
                RETURN n.year as year, count(n) as count
                ORDER BY year DESC
            """)
            
            # By category
            by_category = self.execute_cypher("""
                MATCH (n:NewsArticle)
                WHERE n.category IS NOT NULL
                RETURN n.category as category, count(n) as count
                ORDER BY count DESC
            """)
            
            # Recent articles
            recent = self.execute_cypher("""
                MATCH (n:NewsArticle)
                WHERE n.date IS NOT NULL
                RETURN n.title as title, toString(n.date) as date
                ORDER BY n.date DESC
                LIMIT 5
            """)
            
            return {
                "total_articles": total[0]["total"] if total else 0,
                "by_year": by_year,
                "by_category": by_category,
                "recent_articles": recent
            }
            
        except Exception as e:
            logger.error(f"Failed to get news statistics: {e}")
            raise


def create_driver() -> Driver:
    """Create and return a Neo4j driver instance."""
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
